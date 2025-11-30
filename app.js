/* ============================================================
   GLOBAL STATE
============================================================ */
let rostersData = {};
let scheduleData = {};
let playerStats = {};
let lastProps = [];
let currentFilter = "all";
let viewMode = "expanded"; // "expanded" | "compact"

document.body.classList.add("expandedMode");

/* ============================================================
   VIEW MODE TOGGLE
============================================================ */
document.querySelectorAll(".toggleButton").forEach(btn => {
  btn.addEventListener("click", () => {
    viewMode = btn.dataset.mode;

    document
      .querySelectorAll(".toggleButton")
      .forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    if (viewMode === "compact") {
      document.body.classList.remove("expandedMode");
      document.body.classList.add("compactMode");
    } else {
      document.body.classList.remove("compactMode");
      document.body.classList.add("expandedMode");
    }

    renderProps(); // re-render with new layout
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
   RENDER TODAY'S GAMES
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
      <div>${game.time_et || ""}</div>
    `;
    card.onclick = () => showGameProps(game);
    gamesDiv.appendChild(card);
  });
}

/* ============================================================
   SHOW TEAM ROSTER (sidebar click)
============================================================ */
function showTeamPlayers(team) {
  const panel = document.getElementById("propsOutput");
  panel.innerHTML = `<h3>${team} Roster</h3>`;

  (rostersData[team] || []).forEach(name => {
    const div = document.createElement("div");
    div.textContent = name;
    div.className = "propCard";
    panel.appendChild(div);
  });

  lastProps = [];
}

/* ============================================================
   SHOW PLAYER PROPS FOR A GAME
============================================================ */
function showGameProps(game) {
  const awayPlayers = rostersData[game.away_team] || [];
  const homePlayers = rostersData[game.home_team] || [];

  const entries = [];
  awayPlayers.forEach(name => entries.push(buildProp(name)));
  homePlayers.forEach(name => entries.push(buildProp(name)));

  lastProps = entries;
  renderProps();
}

/* ============================================================
   BUILD SINGLE PLAYER ENTRY
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
  if (!s || s.pts == null) return 0.45;

  let sc = 0.5;
  if (s.usage > 22) sc += 0.1;
  if (s.min > 28) sc += 0.1;
  if (s.def_rank && s.def_rank <= 10) sc += 0.1;
  if (s.def_rank && s.def_rank >= 20) sc -= 0.1;

  return Math.max(0, Math.min(1, sc));
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
    const s = p.stats || {};

    const pts = Number(s.pts ?? 0);
    const reb = Number(s.reb ?? 0);
    const ast = Number(s.ast ?? 0);

    /* Header */
    clone.querySelector(".propName").textContent = p.name;
    clone.querySelector(".propTeam").textContent = s.team || "";

    /* Matchup */
    const opp = s.opponent;
    clone.querySelector(".oppLine").textContent =
      opp ? `${s.team} vs ${opp}` : "No game today";

    clone.querySelector(".oppRank").textContent =
      s.def_rank ? `Defense Rank: ${s.def_rank}` : "";

    /* Season averages text */
    const avgPtsEls = clone.querySelectorAll(".avgPts");
    const avgRebEls = clone.querySelectorAll(".avgReb");
    const avgAstEls = clone.querySelectorAll(".avgAst");

    avgPtsEls.forEach(el => (el.textContent = `PTS: ${pts.toFixed(1)}`));
    avgRebEls.forEach(el => (el.textContent = `REB: ${reb.toFixed(1)}`));
    avgAstEls.forEach(el => (el.textContent = `AST: ${ast.toFixed(1)}`));

    /* Advanced */
    clone.querySelector(".usageLine").textContent =
      `Usage: ${(s.usage ?? 0).toFixed(1)}%`;

    clone.querySelector(".paceLine").textContent =
      `Pace: ${s.pace ?? "N/A"}`;

    /* Records */
    clone.querySelector(".teamRecord").textContent =
      s.team_record || "N/A";

    clone.querySelector(".oppRecord").textContent =
      s.opp_record || "N/A";

    clone.querySelector(".oppStreak").textContent =
      s.opp_streak || "N/A";

    /* Horizontal bars (normalize vs ceilings) */
    const ptsPct = Math.min(100, (pts / 40) * 100);
    const rebPct = Math.min(100, (reb / 15) * 100);
    const astPct = Math.min(100, (ast / 12) * 100);

    const ptsFill = clone.querySelector(".trendPtsFill");
    const rebFill = clone.querySelector(".trendRebFill");
    const astFill = clone.querySelector(".trendAstFill");

    if (ptsFill) ptsFill.style.width = `${isFinite(ptsPct) ? ptsPct : 0}%`;
    if (rebFill) rebFill.style.width = `${isFinite(rebPct) ? rebPct : 0}%`;
    if (astFill) astFill.style.width = `${isFinite(astPct) ? astPct : 0}%`;

    const barPts = clone.querySelector(".barPts");
    const barReb = clone.querySelector(".barReb");
    const barAst = clone.querySelector(".barAst");
    if (barPts) barPts.textContent = pts.toFixed(1);
    if (barReb) barReb.textContent = reb.toFixed(1);
    if (barAst) barAst.textContent = ast.toFixed(1);

    /* Tier pill */
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
    document
      .querySelectorAll(".filterButton")
      .forEach(b => b.classList.remove("filterActive"));
    btn.classList.add("filterActive");
    renderProps();
  };
});
