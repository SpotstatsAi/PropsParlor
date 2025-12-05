// app.js — PropSmith UI Engine (FULL FILE)

/* ---------------------------------------------------------
   CORE CONSTANTS
--------------------------------------------------------- */
const ROSTERS_URL = "https://propsparlor.com/rosters.json";   // your canonical roster source
const PLAYERS_CONTAINER = document.getElementById("players");
const SEARCH_INPUT = document.getElementById("search");
const TEAM_FILTER = document.getElementById("team-filter");

/* ---------------------------------------------------------
   GLOBAL DATA STORE
--------------------------------------------------------- */
let ALL_PLAYERS = [];
let FILTERED_PLAYERS = [];

/* ---------------------------------------------------------
   INIT
--------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", async () => {
  await loadRosters();
  populateTeamFilter();
  renderPlayers(ALL_PLAYERS);

  SEARCH_INPUT.addEventListener("input", runFilters);
  TEAM_FILTER.addEventListener("change", runFilters);
});

/* ---------------------------------------------------------
   LOAD ROSTERS.JSON
--------------------------------------------------------- */
async function loadRosters() {
  try {
    const res = await fetch(ROSTERS_URL, { cache: "no-store" });
    const data = await res.json();

    // Flatten every team’s players into one master array
    ALL_PLAYERS = Object.entries(data).flatMap(([team, players]) =>
      players.map(p => ({
        ...p,
        team,
        full_name: `${p.first_name} ${p.last_name}`.trim()
      }))
    );

    FILTERED_PLAYERS = [...ALL_PLAYERS];
  } catch (err) {
    console.error("Error loading rosters:", err);
  }
}

/* ---------------------------------------------------------
   APPLY FILTERS (SEARCH + TEAM)
--------------------------------------------------------- */
function runFilters() {
  const query = SEARCH_INPUT.value.toLowerCase();
  const team = TEAM_FILTER.value;

  FILTERED_PLAYERS = ALL_PLAYERS.filter(p => {
    const matchesName =
      p.full_name.toLowerCase().includes(query) ||
      p.first_name.toLowerCase().includes(query) ||
      p.last_name.toLowerCase().includes(query);

    const matchesTeam = team === "ALL" || p.team === team;

    return matchesName && matchesTeam;
  });

  renderPlayers(FILTERED_PLAYERS);
}

/* ---------------------------------------------------------
   POPULATE TEAM DROPDOWN
--------------------------------------------------------- */
function populateTeamFilter() {
  const teams = [...new Set(ALL_PLAYERS.map(p => p.team))].sort();

  teams.forEach(team => {
    const opt = document.createElement("option");
    opt.value = team;
    opt.textContent = team;
    TEAM_FILTER.appendChild(opt);
  });
}

/* ---------------------------------------------------------
   RENDER PLAYER CARDS
--------------------------------------------------------- */
function renderPlayers(list) {
  PLAYERS_CONTAINER.innerHTML = "";

  list.forEach(player => {
    const card = document.createElement("div");
    card.className = "player-card";

    card.innerHTML = `
      <div class="player-top">
        <div class="player-name">${player.full_name}</div>
        <div class="player-team">${player.team}</div>
      </div>

      <div class="player-details">
        <span class="player-meta">#${player.jersey_number ?? "--"}</span>
        <span class="player-meta">${player.position ?? "—"}</span>
      </div>

      <button class="select-btn" data-id="${player.player_id}">
        Add to Builder
      </button>
    `;

    PLAYERS_CONTAINER.appendChild(card);
  });

  attachAddEvents();
}

/* ---------------------------------------------------------
   ADD PLAYER BUTTON HANDLER
--------------------------------------------------------- */
function attachAddEvents() {
  document.querySelectorAll(".select-btn").forEach(btn => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      addPlayerToBuilder(id);
    };
  });
}

/* ---------------------------------------------------------
   BUILDER ACTION
--------------------------------------------------------- */
function addPlayerToBuilder(playerId) {
  const p = ALL_PLAYERS.find(pl => pl.player_id == playerId);
  if (!p) return;

  console.log("Added to Prop Builder:", p.full_name);

  // YOU WILL EXPAND THIS SECTION INTO:
  // - stat type picker
  // - thresholds
  // - prop cards
  // - auto suggestions
  // - green/yellow/red prop evaluation
  // For now this only logs.
}

/* ---------------------------------------------------------
   UTILS
--------------------------------------------------------- */
function debounce(fn, ms = 200) {
  let timer;
  return function () {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, arguments), ms);
  };
}
