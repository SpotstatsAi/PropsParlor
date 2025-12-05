// app.js
const state = {
  players: [],
  filtered: [],
  filters: {
    search: "",
    team: "",
    position: "",
    sort: "name-asc",
  },
};

const dom = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheDom();
  bindEvents();
  loadPlayersFromBackend();
});

function cacheDom() {
  dom.playersGrid = document.getElementById("playersGrid");
  dom.playerCount = document.getElementById("playerCount");
  dom.teamCount = document.getElementById("teamCount");
  dom.guardCount = document.getElementById("guardCount");
  dom.forwardCount = document.getElementById("forwardCount");
  dom.centerCount = document.getElementById("centerCount");
  dom.resultSummary = document.getElementById("resultSummary");
  dom.searchInput = document.getElementById("searchInput");
  dom.teamSelect = document.getElementById("teamSelect");
  dom.positionSelect = document.getElementById("positionSelect");
  dom.sortSelect = document.getElementById("sortSelect");
  dom.resetFilters = document.getElementById("resetFilters");
  dom.activeFilters = document.getElementById("activeFilters");
  dom.emptyState = document.getElementById("emptyState");
  dom.errorState = document.getElementById("errorState");
  dom.clearFiltersFromEmpty = document.getElementById("clearFiltersFromEmpty");
}

function bindEvents() {
  dom.searchInput.addEventListener("input", (e) => {
    state.filters.search = e.target.value.trim();
    applyFilters();
  });

  dom.teamSelect.addEventListener("change", (e) => {
    state.filters.team = e.target.value;
    applyFilters();
  });

  dom.positionSelect.addEventListener("change", (e) => {
    state.filters.position = e.target.value;
    applyFilters();
  });

  dom.sortSelect.addEventListener("change", (e) => {
    state.filters.sort = e.target.value;
    applyFilters();
  });

  dom.resetFilters.addEventListener("click", resetFilters);
  dom.clearFiltersFromEmpty.addEventListener("click", resetFilters);
}

async function loadPlayersFromBackend() {
  try {
    dom.resultSummary.textContent = "Loading players…";

    const res = await fetch("/api/players", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const json = await res.json();
    const raw = Array.isArray(json.data) ? json.data : [];

    // Normalize and enrich for client-side filtering/sorting
    state.players = raw.map(enrichPlayer);

    initFiltersFromData();
    updateSummary();
    applyFilters();
  } catch (err) {
    console.error("Error loading players from backend", err);
    dom.errorState.classList.remove("hidden");
    dom.resultSummary.textContent = "Unable to load players.";
  }
}

function enrichPlayer(p) {
  return {
    ...p,
    team: p.team || "",
    pos: p.pos || "",
    jersey: p.jersey || "",
    heightInches: parseHeight(p.height),
    weightNum: p.weight ? Number(p.weight) || null : null,
  };
}

function parseHeight(heightStr) {
  if (!heightStr || typeof heightStr !== "string") return null;
  const match = heightStr.match(/(\d+)-(\d+)/);
  if (!match) return null;
  const feet = parseInt(match[1], 10);
  const inches = parseInt(match[2], 10);
  if (Number.isNaN(feet) || Number.isNaN(inches)) return null;
  return feet * 12 + inches;
}

function initFiltersFromData() {
  const teams = Array.from(
    new Set(
      state.players
        .map((p) => p.team)
        .filter((t) => !!t)
        .sort()
    )
  );
  dom.teamSelect.innerHTML =
    '<option value="">All teams</option>' +
    teams.map((t) => `<option value="${t}">${t}</option>`).join("");

  const positions = Array.from(
    new Set(
      state.players
        .map((p) => p.pos)
        .filter((pos) => !!pos)
        .sort()
    )
  );
  dom.positionSelect.innerHTML =
    '<option value="">All positions</option>' +
    positions.map((pos) => `<option value="${pos}">${pos}</option>`).join("");
}

function updateSummary() {
  dom.playerCount.textContent = state.players.length.toString();

  const teams = new Set(state.players.map((p) => p.team).filter(Boolean));
  dom.teamCount.textContent = teams.size.toString();

  let guards = 0;
  let forwards = 0;
  let centers = 0;
  state.players.forEach((p) => {
    const pos = (p.pos || "").toUpperCase();
    if (!pos) return;
    if (pos.includes("G")) guards += 1;
    if (pos.includes("F")) forwards += 1;
    if (pos.includes("C")) centers += 1;
  });

  dom.guardCount.textContent = guards.toString();
  dom.forwardCount.textContent = forwards.toString();
  dom.centerCount.textContent = centers.toString();
}

function applyFilters() {
  const { search, team, position, sort } = state.filters;

  let filtered = state.players.slice();

  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter((p) => {
      return (
        p.name.toLowerCase().includes(q) ||
        (p.team && p.team.toLowerCase().includes(q)) ||
        (p.jersey && String(p.jersey).toLowerCase().includes(q))
      );
    });
  }

  if (team) {
    filtered = filtered.filter((p) => p.team === team);
  }

  if (position) {
    filtered = filtered.filter((p) => (p.pos || "") === position);
  }

  filtered = sortPlayers(filtered, sort);

  state.filtered = filtered;
  renderPlayers();
  updateResultSummary();
  renderActiveFilters();
}

function sortPlayers(list, sortKey) {
  const arr = list.slice();

  switch (sortKey) {
    case "team":
      arr.sort((a, b) => {
        if (a.team === b.team) {
          return a.last_name.localeCompare(b.last_name);
        }
        return a.team.localeCompare(b.team);
      });
      break;
    case "height-desc":
      arr.sort((a, b) => {
        const ha = a.heightInches ?? -1;
        const hb = b.heightInches ?? -1;
        return hb - ha || a.last_name.localeCompare(b.last_name);
      });
      break;
    case "weight-desc":
      arr.sort((a, b) => {
        const wa = a.weightNum ?? -1;
        const wb = b.weightNum ?? -1;
        return wb - wa || a.last_name.localeCompare(b.last_name);
      });
      break;
    case "jersey-asc":
      arr.sort((a, b) => {
        const ja = parseInt(a.jersey, 10) || 0;
        const jb = parseInt(b.jersey, 10) || 0;
        return ja - jb || a.last_name.localeCompare(b.last_name);
      });
      break;
    case "name-asc":
    default:
      arr.sort((a, b) => a.last_name.localeCompare(b.last_name));
      break;
  }

  return arr;
}

function renderPlayers() {
  dom.playersGrid.innerHTML = "";

  if (!state.filtered.length) {
    dom.emptyState.classList.remove("hidden");
    dom.errorState.classList.add("hidden");
    return;
  }

  dom.emptyState.classList.add("hidden");
  dom.errorState.classList.add("hidden");

  const fragment = document.createDocumentFragment();

  state.filtered.forEach((p) => {
    const card = document.createElement("article");
    card.className = "player-card";

    const playerHeight = p.height || "—";
    const playerWeight = p.weight ? `${p.weight} lb` : "—";
    const jerseyText = p.jersey ? `#${p.jersey}` : "--";

    card.innerHTML = `
      <div class="player-card-header">
        <div class="player-name-block">
          <div class="player-name">${p.first_name} ${p.last_name}</div>
          <div class="player-meta-line">
            <span>${p.pos || "N/A"}</span>
            <span>•</span>
            <span>ID ${p.id}</span>
          </div>
          <div class="player-tagline">Always available • Player-only view</div>
        </div>
        <div class="team-pill">${p.team || "FA"}</div>
      </div>
      <div class="player-body">
        <div class="player-attrs">
          <div class="attr-block">
            <span>Height</span>
            <strong>${playerHeight}</strong>
          </div>
          <div class="attr-block">
            <span>Weight</span>
            <strong>${playerWeight}</strong>
          </div>
          <div class="attr-block">
            <span>Jersey</span>
            <strong>${jerseyText}</strong>
          </div>
        </div>
        <div class="jersey-pill">${jerseyText}</div>
      </div>
    `;

    fragment.appendChild(card);
  });

  dom.playersGrid.appendChild(fragment);
}

function updateResultSummary() {
  const total = state.players.length;
  const count = state.filtered.length;

  if (!total) {
    dom.resultSummary.textContent = "No players loaded.";
    return;
  }

  if (count === total) {
    dom.resultSummary.textContent = `${count} players • All teams • No game context required`;
  } else {
    dom.resultSummary.textContent = `${count} / ${total} players match current filters`;
  }
}

function renderActiveFilters() {
  const chips = [];

  if (state.filters.search) {
    chips.push({
      key: "search",
      label: "Search",
      value: state.filters.search,
    });
  }

  if (state.filters.team) {
    chips.push({
      key: "team",
      label: "Team",
      value: state.filters.team,
    });
  }

  if (state.filters.position) {
    chips.push({
      key: "position",
      label: "Position",
      value: state.filters.position,
    });
  }

  if (state.filters.sort && state.filters.sort !== "name-asc") {
    chips.push({
      key: "sort",
      label: "Sort",
      value: mapSortKeyToLabel(state.filters.sort),
    });
  }

  dom.activeFilters.innerHTML = "";

  if (!chips.length) return;

  const fragment = document.createDocumentFragment();

  chips.forEach((chip) => {
    const el = document.createElement("div");
    el.className = "chip";
    el.innerHTML = `
      <small>${chip.label}</small>
      <span>${escapeHtml(chip.value)}</span>
      <button type="button" aria-label="Clear ${chip.label} filter">&times;</button>
    `;

    el.querySelector("button").addEventListener("click", () => {
      clearFilterKey(chip.key);
    });

    fragment.appendChild(el);
  });

  dom.activeFilters.appendChild(fragment);
}

function clearFilterKey(key) {
  switch (key) {
    case "search":
      state.filters.search = "";
      dom.searchInput.value = "";
      break;
    case "team":
      state.filters.team = "";
      dom.teamSelect.value = "";
      break;
    case "position":
      state.filters.position = "";
      dom.positionSelect.value = "";
      break;
    case "sort":
      state.filters.sort = "name-asc";
      dom.sortSelect.value = "name-asc";
      break;
    default:
      break;
  }
  applyFilters();
}

function resetFilters() {
  state.filters.search = "";
  state.filters.team = "";
  state.filters.position = "";
  state.filters.sort = "name-asc";

  dom.searchInput.value = "";
  dom.teamSelect.value = "";
  dom.positionSelect.value = "";
  dom.sortSelect.value = "name-asc";

  applyFilters();
}

function mapSortKeyToLabel(key) {
  switch (key) {
    case "team":
      return "Team, then name";
    case "height-desc":
      return "Height (tallest)";
    case "weight-desc":
      return "Weight (heaviest)";
    case "jersey-asc":
      return "Jersey #";
    case "name-asc":
    default:
      return "Name A → Z";
  }
}

function escapeHtml(unsafe) {
  return String(unsafe)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
