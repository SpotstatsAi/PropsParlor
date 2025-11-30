/* ----------------------------------------------------
   NBA PROP ENGINE — FULLY REWRITTEN MAIN APP SCRIPT
   Clean • Optimized • Supports Tier Styling + Charts
----------------------------------------------------- */

let rostersData = {};
let scheduleData = {};
let playerStats = {};
let lastProps = [];
let currentFilter = "all";

/* ----------------------------------------------------
   LOAD DATA
----------------------------------------------------- */
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
    console.error("Load error:", err);
    alert("Failed loading engine data.");
  }
}

/* ----------------------------------------------------
   SIDEBAR: TEAMS LIST
----------------------------------------------------- */
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

/* ----------------------------------------------------
   TODAY'S GAMES
----------------------------------------------------- */
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

/* ----------------------------------------------------
   TEAM PAGE (LEFT SIDE)
----------------------------------------------------- */
function showTeamPlayers(team) {
  const panel = document.getElementById("propsOutput");
  panel.innerHTML = `<h3>${team} Roster</h3>`;

  (rostersData[team] || []).forEach(name => {
    const row = document.createElement("div");
    row.className = "teamListPlayer";
    row.textContent = name;
    panel.appendChild(row);
  });

  lastProps = [];
}

/* ----------------------------------------------------
   GAME CLICK → BUILD PROP LIST
----------------------------------------------------- */
function showGameProps(game) {
  const away = rostersData[game.away_team] || [];
  const home = rostersData[game.home_team] || [];

  const entries = [];
  away.forEach(n => entries.push(buildProp(n)));
  home.forEach(n => entries.push(buildProp(n)));

  lastProps = entries;
  renderProps();
}

/* ----------------------------------------------------
   BUILD A SINGLE PLAYER PROP OBJECT
----------------------------------------------------- */
function buildProp(name) {
  const stats = playerStats[name] || {};
  const score = scorePlayer(stats);

  let tier = "RED";
  if (score >= 0.75) tier = "GREEN";
  else if (score >= 0.55) tier = "YELLOW";

  return { name, stats, tier, score };
}

/* ----------------------------------------------------
   TIER SCORE LOGIC
----------------------------------------------------- */
function scorePlayer(s) {
  if (!s || !s.pts || s.games === 0) return 0.45;

  let sc = 0.5;

  if (s.usage > 22) sc += 0.1;
  if (s.min > 28) sc += 0.1;
  if (s.def_rank && s.def_rank <= 10) sc += 0.1;
  if (s.def_rank && s.def_rank >= 20) sc -= 0.1;

  return Math.max(0, Math.min(1, sc));
}

/* ----------------------------------------------------
   RENDER PLAYER PROP CARDS
----------------------------------------------------- */
function renderProps() {
  const panel = document.getElementById("propsOutput");
  const template = document.getElementById("propRowTemplate");

  panel.innerHTML = "";
  if (!template) return;

  const filtered = lastProps.filter(p =>
    currentFilter === "all" ? true : p.tier === currentFilter.toUpperCase()
  );

  filtered.sort((a, b) => b.score - a.score);

  filtered.forEach(p => {
    const clone = document.importNode(template.content, true);
    const card = clone.querySelector(".propCard");
    const s = p.stats || {};

    /* --- Add tier class for left accent & glow --- */
    if (card) card.classList.add(`tier${p.tier}`);

    /* --- Header ---- */
    clone.querySelector(".propName").textContent = p.name;
    clone.querySelector(".propTeam").textContent = s.team || "";

    /* --- Opponent section --- */
    const opp = s.opponent;
    clone.querySelector(".oppLine").textContent =
      opp ? `${s.team} vs ${opp}` : "No game today";

    clone.querySelector(".oppRank").textContent =
      s.def_rank ? `Defense Rank: ${s.def_rank}` : "";

    /* --- Season averages --- */
    clone.querySelector(".avgPts").textContent = `PTS: ${(s.pts ?? 0).toFixed(1)}`;
    clone.querySelector(".avgReb").textContent = `REB: ${(s.reb ?? 0).toFixed(1)}`;
    clone.querySelector(".avgAst").textContent = `AST: ${(s.ast ?? 0).toFixed(1)}`;

    /* --- Advanced --- */
    clone.querySelector(".usageLine").textContent =
      `USG: ${(s.usage ?? 0).toFixed(1)}%`;

    clone.querySelector(".paceLine").textContent =
      `Pace: ${s.pace ?? "N/A"}`;

    /* --- Record --- */
    clone.querySelector(".teamRecord").textContent =
      s.team_record || "N/A";

    clone.querySelector(".oppRecord").textContent =
      s.opp_record || "N/A";

    clone.querySelector(".oppStreak").textContent =
      s.opp_streak ? `Streak: ${s.opp_streak}` : `Streak: N/A`;

    /* --- Trend bars (mini analytics) --- */
    const ptsFill = clone.querySelector(".trendPtsFill");
    const rebFill = clone.querySelector(".trendRebFill");
    const astFill = clone.querySelector(".trendAstFill");

    const ptsPct = Math.min(100, (s.pts / 40) * 100);
    const rebPct = Math.min(100, (s.reb / 15) * 100);
    const astPct = Math.min(100, (s.ast / 12) * 100);

    if (ptsFill) ptsFill.style.width = ptsPct + "%";
    if (rebFill) rebFill.style.width = rebPct + "%";
    if (astFill) astFill.style.width = astPct + "%";

    /* --- Tier pill --- */
    const tag = clone.querySelector(".tierTag");
    if (tag) {
      tag.textContent = p.tier;
      tag.classList.add(
        p.tier === "GREEN" ? "tier-green" :
        p.tier === "YELLOW" ? "tier-yellow" :
        "tier-red"
      );
    }

    panel.appendChild(clone);
  });
}

/* ----------------------------------------------------
   FILTER BUTTONS
----------------------------------------------------- */
document.querySelectorAll(".filterButton").forEach(btn => {
  btn.onclick = () => {
    currentFilter = btn.dataset.filter;

    document.querySelectorAll(".filterButton")
      .forEach(b => b.classList.remove("filterActive"));

    btn.classList.add("filterActive");

    renderProps();
  };
});

/* ----------------------------------------------------
   INIT
----------------------------------------------------- */
document.getElementById("loadButton").onclick = loadData;
