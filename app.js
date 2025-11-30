//------------------------------------------------------
// GLOBAL STATE
//------------------------------------------------------
let rostersData = {};
let scheduleData = {};
let playerStats = {};
let lastProps = [];
let currentFilter = "all";

//------------------------------------------------------
// LOAD DATA
//------------------------------------------------------
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

    renderGames();
    renderTeams();
  } catch (err) {
    console.error(err);
    alert("Failed loading engine data.");
  }
}

//------------------------------------------------------
// SIDEBAR RENDER
//------------------------------------------------------
function renderGames() {
  const gamesDiv = document.getElementById("games");
  gamesDiv.innerHTML = "";

  const today = new Date().toISOString().split("T")[0];
  const games = scheduleData[today] || [];

  if (!games.length) {
    gamesDiv.innerHTML = `<p>No games today</p>`;
    return;
  }

  games.forEach(game => {
    const card = document.createElement("div");
    card.className = "gameCard";

    card.innerHTML = `
      <strong>${game.away_team} @ ${game.home_team}</strong>
      <div>${game.time_et}</div>
    `;

    card.addEventListener("click", () => showGameProps(game));
    gamesDiv.appendChild(card);
  });
}

function renderTeams() {
  const container = document.getElementById("teamsList");
  container.innerHTML = "";

  Object.keys(rostersData).forEach(team => {
    const div = document.createElement("div");
    div.className = "teamEntry";
    div.textContent = team;
    div.addEventListener("click", () => showTeamPlayers(team));
    container.appendChild(div);
  });
}

//------------------------------------------------------
// BUILD PLAYER OBJECT
//------------------------------------------------------
function buildProp(name) {
  const s = playerStats[name] || {};

  const confidence = computeConfidenceScore(s);
  const tier =
    confidence >= 75 ? "GREEN" :
    confidence >= 55 ? "YELLOW" :
    "RED";

  return { name, stats: s, tier, confidence };
}

//------------------------------------------------------
// CONFIDENCE ENGINE (0–100)
//------------------------------------------------------
function computeConfidenceScore(s) {
  if (!s || !s.pts) return 20;

  let score = 50; // baseline neutral

  // Usage (weight 15)
  score += clamp(s.usage * 0.6, -10, 15);

  // Minutes (weight 15)
  if (s.min >= 34) score += 15;
  else if (s.min >= 28) score += 8;
  else score -= 4;

  // Opponent defense (weight 10)
  if (s.def_rank) {
    if (s.def_rank <= 8) score -= 8;
    else if (s.def_rank >= 22) score += 6;
  }

  // Last-5 trend (weight 20)
  if (Array.isArray(s.trend_pts) && s.trend_pts.length) {
    const last5 = avg(s.trend_pts);
    const delta = last5 - s.pts;

    if (delta > 3) score += 15;
    else if (delta > 1.5) score += 8;
    else if (delta < -3) score -= 12;
  }

  // Volume & role (weight 10)
  if (s.min >= 32 && s.usage >= 24) score += 10;

  // Opponent streak (weight 5)
  if (s.opp_streak && s.opp_streak.startsWith("L")) score += 3;
  if (s.opp_streak && s.opp_streak.startsWith("W")) score -= 3;

  return clamp(score, 0, 100);
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function avg(arr) {
  if (!arr || !arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

//------------------------------------------------------
// SHOW GAME → BUILD PROPS
//------------------------------------------------------
function showGameProps(game) {
  const awayList = rostersData[game.away_team] || [];
  const homeList = rostersData[game.home_team] || [];

  const entries = [];
  awayList.forEach(name => entries.push(buildProp(name)));
  homeList.forEach(name => entries.push(buildProp(name)));

  lastProps = entries;
  renderProps();
}

function showTeamPlayers(team) {
  const panel = document.getElementById("propsOutput");
  panel.innerHTML = `<h3>${team} Roster</h3>`;
  (rostersData[team] || []).forEach(p => {
    panel.innerHTML += `<div>${p}</div>`;
  });
  lastProps = [];
}

//------------------------------------------------------
// SAFE RENDER PLAYER CARDS (WORKS EVEN IF FIELDS MISSING)
//------------------------------------------------------
function renderProps() {
  const panel = document.getElementById("propsOutput");
  const template = document.getElementById("propRowTemplate");

  panel.innerHTML = "";

  const visible = lastProps.filter(p => {
    if (currentFilter === "all") return true;
    return p.tier === currentFilter.toUpperCase();
  });

  visible.sort((a, b) => b.confidence - a.confidence);

  visible.forEach(p => {
    const clone = document.importNode(template.content, true);
    const s = p.stats || {};

    // NAME + TEAM
    clone.querySelector(".propName").textContent = p.name;
    clone.querySelector(".propTeam").textContent = s.team ?? "—";

    // CONFIDENCE
    clone.querySelector(".confidenceValue").textContent =
      p.confidence ?? 0;

    const tier = p.tier || "RED";
    const pill = clone.querySelector(".tierTag");
    pill.textContent = tier;
    pill.classList.remove("tier-green", "tier-yellow", "tier-red");
    if (tier === "GREEN") pill.classList.add("tier-green");
    else if (tier === "YELLOW") pill.classList.add("tier-yellow");
    else pill.classList.add("tier-red");

    // MATCHUP
    clone.querySelector(".oppLine").textContent =
      `${s.team ?? "—"} vs ${s.opponent ?? "—"}`;
    clone.querySelector(".oppRank").textContent =
      `Defense rank: #${s.def_rank ?? "—"}`;
    clone.querySelector(".oppStreak").textContent =
      `Opp streak: ${s.opp_streak ?? "—"}`;

    // SEASON AVG
    clone.querySelector(".avgPts").textContent = (s.pts ?? 0).toFixed(1);
    clone.querySelector(".avgReb").textContent = (s.reb ?? 0).toFixed(1);
    clone.querySelector(".avgAst").textContent = (s.ast ?? 0).toFixed(1);

    // SAFE BARS
    setBarWidth(clone.querySelector(".trendPtsFill"), s.pts, 40);
    setBarWidth(clone.querySelector(".trendRebFill"), s.reb, 20);
    setBarWidth(clone.querySelector(".trendAstFill"), s.ast, 15);

    panel.appendChild(clone);
  });
}

//------------------------------------------------------
// SAFE BAR WIDTH
//------------------------------------------------------
function setBarWidth(bar, val = 0, max) {
  if (!bar) return;
  const pct = Math.min(100, Math.max(0, (val / max) * 100));
  bar.style.width = pct + "%";
}

//------------------------------------------------------
// FILTER BUTTONS
//------------------------------------------------------
document.querySelectorAll(".filterButton").forEach(btn => {
  btn.addEventListener("click", () => {
    currentFilter = btn.dataset.filter;
    document.querySelectorAll(".filterButton")
      .forEach(b => b.classList.remove("filterActive"));
    btn.classList.add("filterActive");
    renderProps();
  });
});

//------------------------------------------------------
// LOAD BUTTON
//------------------------------------------------------
document.getElementById("loadButton").addEventListener("click", loadData);
