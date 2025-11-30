/* ============================================================
   GLOBAL STATE
============================================================ */
let rostersData = {};
let scheduleData = {};
let playerStats = {};
let lastProps = [];
let currentFilter = "all";
let viewMode = "expanded"; // expanded | compact

document.body.classList.add("expandedMode");

/* ============================================================
   VIEW MODE TOGGLE
============================================================ */
document.querySelectorAll(".toggleButton").forEach(btn => {
  btn.addEventListener("click", () => {
    viewMode = btn.dataset.mode;

    document.querySelectorAll(".toggleButton")
      .forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    if (viewMode === "compact") {
      document.body.classList.remove("expandedMode");
      document.body.classList.add("compactMode");
    } else {
      document.body.classList.remove("compactMode");
      document.body.classList.add("expandedMode");
    }

    renderProps();
  });
});


/* ============================================================
   DATA LOADING
============================================================ */
async function loadData() {
  try {
    const [rosters, schedule, stats] = await Promise.all([
      fetch("rosters.json").then(r => r.json()),
      fetch("schedule.json").then(r => r.json()),
      fetch("player_stats.json").then(r => r.json())
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

document.getElementById("loadButton").onclick = loadData;


/* ============================================================
   RENDER TEAMS
============================================================ */
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


/* ============================================================
   RENDER GAMES
============================================================ */
function renderGames() {
  const gamesDiv = document.getElementById("games");
  gamesDiv.innerHTML = "";

  const today = new Date().toISOString().split("T")[0];
  const games = scheduleData[today] || [];

  if (!games.length) {
    gamesDiv.innerHTML = "<p>No games today</p>";
    return;
  }

  games.forEach(game => {
    const card = document.createElement("div");
    card.className = "gameCard";
    card.innerHTML = `
      <strong>${game.away_team} @ ${game.home_team}</strong>
      <div>${game.time_et}</div>
    `;
    card.onclick = () => showGameProps(game);
    gamesDiv.appendChild(card);
  });
}


/* ============================================================
   SHOW TEAM ROSTER
============================================================ */
function showTeamPlayers(team) {
  const panel = document.getElementById("propsOutput");
  panel.innerHTML = `<h3>${team} Roster</h3>`;

  (rostersData[team] || []).forEach(name => {
    const div = document.createElement("div");
    div.textContent = name;
    div.className = "propCard smallCard";
    panel.appendChild(div);
  });

  lastProps = [];
}


/* ============================================================
   SHOW PLAYER PROPS FOR GAME
============================================================ */
function showGameProps(game) {
  const away = rostersData[game.away_team] || [];
  const home = rostersData[game.home_team] || [];

  const entries = [];
  away.forEach(n => entries.push(buildProp(n)));
  home.forEach(n => entries.push(buildProp(n)));

  lastProps = entries;
  renderProps();
}


/* ============================================================
   BUILD SINGLE PROP
============================================================ */
function buildProp(name) {
  const stats = playerStats[name] || {};
  const score = scorePlayer(stats);

  let tier = "RED";
  if (score >= 0.75) tier = "GREEN";
  else if (score >= 0.55) tier = "YELLOW";

  return { name, stats, tier, score };
}


/* ============================================================
   SCORING LOGIC
============================================================ */
function scorePlayer(s) {
  if (!s || !s.pts) return 0.45;

  let sc = 0.5;
  if (s.usage > 22) sc += 0.1;
  if (s.min > 28) sc += 0.1;
  if (s.def_rank && s.def_rank <= 10) sc += 0.1;
  if (s.def_rank && s.def_rank >= 20) sc -= 0.1;

  return Math.max(0, Math.min(1, sc));
}


/* ============================================================
   MINI CHART GENERATOR (SPARKLINES)
============================================================ */
function generateSparkline(values) {
  if (!values || values.length === 0) return "";

  const max = Math.max(...values);
  const min = Math.min(...values);
  const scale = max - min || 1;

  return values
    .map(v => {
      const pct = ((v - min) / scale) * 100;
      return `<div class="sparkBar" style="height:${pct}%"></div>`;
    })
    .join("");
}


/* ============================================================
   RENDER PLAYER CARDS
============================================================ */
function renderProps() {
  const panel = document.getElementById("propsOutput");
  const template = document.getElementById("propRowTemplate");
  if (!template) return;

  panel.innerHTML = "";

  const filtered = lastProps.filter(p => {
    if (currentFilter === "all") return true;
    return p.tier === currentFilter.toUpperCase();
  });

  filtered.sort((a, b) => b.score - a.score);

  filtered.forEach(p => {
    const clone = document.importNode(template.content, true);
    const s = p.stats;

    /* Header */
    clone.querySelector(".propName").textContent = p.name;
    clone.querySelector(".propTeam").textContent = s.team;

    /* Matchup */
    clone.querySelector(".oppLine").textContent =
      s.opponent ? `${s.team} vs ${s.opponent}` : "No game today";

    clone.querySelector(".oppRank").textContent =
      s.def_rank ? `Defense Rank: ${s.def_rank}` : "";

    /* Season averages */
    clone.querySelector(".avgPts").textContent = `${s.pts?.toFixed(1)}`;
    clone.querySelector(".avgReb").textContent = `${s.reb?.toFixed(1)}`;
    clone.querySelector(".avgAst").textContent = `${s.ast?.toFixed(1)}`;

    /* Advanced */
    clone.querySelector(".usageLine").textContent =
      `${s.usage?.toFixed(1) || 0}%`;
    clone.querySelector(".paceLine").textContent =
      `${s.pace ?? "N/A"}`;

    /* Records */
    clone.querySelector(".teamRecord").textContent =
      s.team_record || "N/A";

    clone.querySelector(".oppRecord").textContent =
      s.opp_record || "N/A";

    clone.querySelector(".oppStreak").textContent =
      s.opp_streak || "N/A";

    /* Trend charts (fallback auto-generated) */
    const pts10 = s.trend_pts || [s.pts, s.pts, s.pts, s.pts, s.pts, s.pts, s.pts];
    const reb10 = s.trend_reb || [s.reb, s.reb, s.reb, s.reb, s.reb, s.reb, s.reb];
    const ast10 = s.trend_ast || [s.ast, s.ast, s.ast, s.ast, s.ast, s.ast, s.ast];

    clone.querySelector(".sparkPts").innerHTML = generateSparkline(pts10);
    clone.querySelector(".sparkReb").innerHTML = generateSparkline(reb10);
    clone.querySelector(".sparkAst").innerHTML = generateSparkline(ast10);

    /* Tier */
    const tag = clone.querySelector(".tierTag");
    tag.textContent = p.tier;
    tag.classList.add(`tier-${p.tier.toLowerCase()}`);

    panel.appendChild(clone);
  });
}


/* ============================================================
   FILTER BUTTONS
============================================================ */
document.querySelectorAll(".filterButton").forEach(btn => {
  btn.onclick = () => {
    currentFilter = btn.dataset.filter;
    document.querySelectorAll(".filterButton")
      .forEach(b => b.classList.remove("filterActive"));
    btn.classList.add("filterActive");
    renderProps();
  };
});
