let rostersData = {};
let scheduleData = {};
let playerStats = {};
let lastProps = [];
let currentFilter = "all";

// Utility: team logos
const TEAM_LOGO = code =>
  `https://a.espncdn.com/i/teamlogos/nba/500/${code.toLowerCase()}.png`;

// Utility: player headshots (fallback)
const PLAYER_IMG = name =>
  `https://a.espncdn.com/i/headshots/nba/players/full/${name.replace(/ /g, "_")}.png`;

// ---------------------------------------------------------
// LOAD DATA
// ---------------------------------------------------------
async function loadData() {
  try {
    const [rosters, schedule, stats] = await Promise.all([
      fetch("rosters.json").then(r => r.json()),
      fetch("schedule.json").then(r => r.json()),
      fetch("player_stats.json").then(r => r.json()),
    ]);

    rostersData = rosters;
    scheduleData = schedule;
    playerStats = stats;

    renderTeams();
    renderGames();
  } catch (err) {
    console.error(err);
    alert("Failed loading engine data.");
  }
}

// ---------------------------------------------------------
// UI BUILDERS
// ---------------------------------------------------------
function renderTeams() {
  const container = document.getElementById("teamsList");
  container.innerHTML = "";

  Object.keys(rostersData).forEach(team => {
    const div = document.createElement("div");
    div.className = "teamEntry";
    div.textContent = team;
    div.onclick = () => showTeamPlayers(team);
    container.appendChild(div);
  });
}

function renderGames() {
  const panel = document.getElementById("games");
  panel.innerHTML = "";

  const today = new Date().toISOString().split("T")[0];
  const games = scheduleData[today] || [];

  games.forEach(game => {
    const el = document.createElement("div");
    el.className = "gameCard";
    el.innerHTML = `<strong>${game.away_team} @ ${game.home_team}</strong>
                    <div>${game.time_et}</div>`;
    el.onclick = () => showGameProps(game);
    panel.appendChild(el);
  });
}

// ---------------------------------------------------------
// GAME PROPS
// ---------------------------------------------------------
function showGameProps(game) {
  const entries = [];
  (rostersData[game.away_team] || []).forEach(n => entries.push(buildProp(n)));
  (rostersData[game.home_team] || []).forEach(n => entries.push(buildProp(n)));

  lastProps = entries;
  renderProps();
}

function buildProp(name) {
  const s = playerStats[name] || {};
  const score = scorePlayer(s);
  let tier = score >= 0.75 ? "GREEN" : score >= 0.55 ? "YELLOW" : "RED";

  return { name, stats: s, tier, score };
}

// ---------------------------------------------------------
// SCORING LOGIC
// ---------------------------------------------------------
function scorePlayer(s) {
  if (!s || !s.pts) return 0.45;

  let sc = 0.5;

  if (s.usage > 22) sc += 0.1;
  if (s.min > 28) sc += 0.1;
  if (s.def_rank <= 10) sc += 0.1;

  return Math.max(0, Math.min(1, sc));
}

// ---------------------------------------------------------
// RENDER PLAYER CARDS
// ---------------------------------------------------------
function renderProps() {
  const panel = document.getElementById("propsOutput");
  const template = document.getElementById("propRowTemplate");

  panel.innerHTML = "";

  const filtered = lastProps.filter(p =>
    currentFilter === "all" ? true : p.tier === currentFilter.toUpperCase()
  );

  filtered.sort((a, b) => b.score - a.score);

  filtered.forEach(p => {
    const clone = document.importNode(template.content, true);
    const s = p.stats;

    // Header
    clone.querySelector(".propName").textContent = p.name;
    clone.querySelector(".propTeam").textContent = s.team;

    // Headshot + Logo
    clone.querySelector(".playerHeadshot").src = PLAYER_IMG(p.name);
    clone.querySelector(".teamLogo").src = TEAM_LOGO(s.team);

    // Matchup
    clone.querySelector(".oppLine").textContent =
      s.opponent ? `${s.team} vs ${s.opponent}` : "No Game";

    clone.querySelector(".oppRank").textContent =
      s.def_rank ? `Defense Rank: ${s.def_rank}` : "";

    // DEFENSE BAR
    const pct = s.def_rank ? (32 - s.def_rank) / 32 : 0;
    clone.querySelector(".defBarInner").style.width = `${pct * 100}%`;

    // Season Avg
    clone.querySelector(".avgPts").textContent = `PTS: ${s.pts?.toFixed(1)}`;
    clone.querySelector(".avgReb").textContent = `REB: ${s.reb?.toFixed(1)}`;
    clone.querySelector(".avgAst").textContent = `AST: ${s.ast?.toFixed(1)}`;

    // Advanced
    clone.querySelector(".usageLine").textContent =
      `USG: ${s.usage?.toFixed(1)}%`;

    clone.querySelector(".paceLine").textContent =
      `Pace: ${s.pace ?? "N/A"}`;

    // Records
    clone.querySelector(".teamRecord").textContent =
      `Team Record: ${s.team_record || "N/A"}`;

    clone.querySelector(".oppRecord").textContent =
      `Opponent Record: ${s.opp_record || "N/A"}`;

    clone.querySelector(".oppStreak").textContent =
      `Streak: ${s.opp_streak || "N/A"}`;

    // Chart
    const chartEl = clone.querySelector(".playerChart");
    buildMiniChart(chartEl, p);

    // Tier
    const tag = clone.querySelector(".tierTag");
    tag.textContent = p.tier;
    tag.classList.add(
      p.tier === "GREEN"
        ? "tier-green"
        : p.tier === "YELLOW"
        ? "tier-yellow"
        : "tier-red"
    );

    // Expand collapse
    const col = clone.querySelector(".collapsible");
    const title = col.querySelector(".sectionTitle");
    const content = col.querySelector(".collapseContent");

    title.onclick = () => {
      content.classList.toggle("open");
      title.textContent = content.classList.contains("open")
        ? "Team & Opponent Details ▲"
        : "Team & Opponent Details ▼";
    };

    panel.appendChild(clone);
  });
}

// ---------------------------------------------------------
// MINI CHART
// ---------------------------------------------------------
function buildMiniChart(canvas, prop) {
  const randomData = [
    Math.random() * 10 + prop.stats.pts,
    Math.random() * 10 + prop.stats.pts,
    Math.random() * 10 + prop.stats.pts,
    Math.random() * 10 + prop.stats.pts,
    prop.stats.pts,
  ]; // Placeholder until we load real game logs

  new Chart(canvas, {
    type: "line",
    data: {
      labels: ["G1", "G2", "G3", "G4", "G5"],
      datasets: [
        {
          data: randomData,
          borderColor: "#3d7bff",
          fill: false,
          tension: 0.3,
        },
      ],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { display: false },
      },
    },
  });
}

// ---------------------------------------------------------
// FILTERS
// ---------------------------------------------------------
document.querySelectorAll(".filterButton").forEach(btn => {
  btn.onclick = () => {
    currentFilter = btn.dataset.filter;
    document.querySelectorAll(".filterButton").forEach(b => b.classList.remove("filterActive"));
    btn.classList.add("filterActive");
    renderProps();
  };
});

document.getElementById("loadButton").onclick = loadData;
