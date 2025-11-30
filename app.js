let rostersData = {};
let scheduleData = {};
let playerStats = {};
let lastProps = [];
let currentFilter = "all";
let currentView = "expanded";

// Load all JSON assets
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
    lastProps = [];
    renderProps();
  } catch (err) {
    console.error(err);
    alert("Failed loading engine data.");
  }
}

// Sidebar: games
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

// Sidebar: teams
function renderTeams() {
  const list = document.getElementById("teamsList");
  list.innerHTML = "";

  Object.keys(rostersData)
    .sort()
    .forEach(team => {
      const div = document.createElement("div");
      div.className = "teamEntry";
      div.textContent = team;
      div.onclick = () => showTeamPlayers(team);
      list.appendChild(div);
    });
}

// Show all players on a team
function showTeamPlayers(team) {
  const players = rostersData[team] || [];
  lastProps = players.map(name => buildProp(name));
  renderProps();
}

// Show all props for a given game
function showGameProps(game) {
  const awayPlayers = rostersData[game.away_team] || [];
  const homePlayers = rostersData[game.home_team] || [];

  const entries = [];
  awayPlayers.forEach(n => entries.push(buildProp(n)));
  homePlayers.forEach(n => entries.push(buildProp(n)));

  lastProps = entries;
  renderProps();
}

// Build a single "prop object"
function buildProp(name) {
  const stats = playerStats[name] || {};
  const confidence = stats.confidence ?? 50;

  let tier = "RED";
  if (confidence >= 80) tier = "GREEN";
  else if (confidence >= 60) tier = "YELLOW";

  return { name, stats, tier, confidence };
}

// Render props list
function renderProps() {
  const panel = document.getElementById("propsOutput");
  const template = document.getElementById("propRowTemplate");
  panel.innerHTML = "";
  if (!template) return;

  const filtered = lastProps.filter(p => {
    if (currentFilter === "all") return true;
    return p.tier === currentFilter.toUpperCase();
  });

  // Sort by confidence descending
  filtered.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));

  filtered.forEach(p => {
    const clone = document.importNode(template.content, true);
    const card = clone.querySelector(".propCard");
    const s = p.stats || {};

    if (currentView === "compact") {
      card.classList.add("compact");
      card.dataset.view = "compact";
    } else {
      card.classList.remove("compact");
      card.dataset.view = "expanded";
    }

    // Header
    clone.querySelector(".propName").textContent = p.name;
    clone.querySelector(".propTeam").textContent = s.team || "";

    const confEl = clone.querySelector(".confidenceValue");
    if (confEl) confEl.textContent = Math.round(p.confidence || 0);

    const tierTag = clone.querySelector(".tierTag");
    if (tierTag) {
      tierTag.textContent = s.rec_tag || p.tier;
      tierTag.classList.remove("tier-green", "tier-yellow", "tier-red");
      if (p.tier === "GREEN") tierTag.classList.add("tier-green");
      else if (p.tier === "YELLOW") tierTag.classList.add("tier-yellow");
      else tierTag.classList.add("tier-red");
    }

    // Matchup block
    const opp = s.opponent;
    const oppLine = clone.querySelector(".oppLine");
    const oppRank = clone.querySelector(".oppRank");
    const smiFill = clone.querySelector(".smiFill");
    const smiText = clone.querySelector(".smiText");

    if (oppLine) {
      oppLine.textContent = opp ? `${s.team} vs ${opp}` : "No game today";
    }
    if (oppRank) {
      oppRank.textContent = s.def_rank
        ? `Defense Rank: ${s.def_rank}`
        : "Defense Rank: N/A";
    }

    const smi = s.smi ?? 0.5;
    const smiPct = Math.round(smi * 100);
    if (smiFill) smiFill.style.width = `${smiPct}%`;

    let smiLabel = "Average";
    if (smi >= 0.7) smiLabel = "Strong matchup";
    else if (smi <= 0.35) smiLabel = "Tough matchup";

    if (smiText) smiText.textContent = `${smiLabel} (${smiPct})`;

    // Season vs last 5
    const pts = s.pts ?? 0;
    const reb = s.reb ?? 0;
    const ast = s.ast ?? 0;

    const l5_pts = s.l5_pts ?? pts;
    const l5_reb = s.l5_reb ?? reb;
    const l5_ast = s.l5_ast ?? ast;

    const avgSummary = clone.querySelector(".avgSummary");
    if (avgSummary) {
      avgSummary.textContent = `Season: ${pts.toFixed(
        1
      )}/${reb.toFixed(1)}/${ast.toFixed(1)} · L5: ${l5_pts.toFixed(
        1
      )}/${l5_reb.toFixed(1)}/${l5_ast.toFixed(1)} (PTS/REB/AST)`;
    }

    fillTrend(
      clone,
      "Pts",
      pts,
      l5_pts,
      s.trend_pts,
      s.cons_pts,
      40 // rough max
    );
    fillTrend(
      clone,
      "Reb",
      reb,
      l5_reb,
      s.trend_reb,
      s.cons_reb,
      18
    );
    fillTrend(
      clone,
      "Ast",
      ast,
      l5_ast,
      s.trend_ast,
      s.cons_ast,
      12
    );

    // Advanced block
    const usageLine = clone.querySelector(".usageLine");
    const paceLine = clone.querySelector(".paceLine");
    const teamRecord = clone.querySelector(".teamRecord");
    const oppRecord = clone.querySelector(".oppRecord");
    const oppStreak = clone.querySelector(".oppStreak");
    const consLine = clone.querySelector(".consistencyLine");

    if (usageLine) {
      const u = s.usage ?? 0;
      usageLine.textContent = `Usage: ${u.toFixed(1)}%`;
    }

    if (paceLine) {
      paceLine.textContent = `Possessions: ${
        s.pace != null ? s.pace : "N/A"
      }`;
    }

    if (teamRecord) {
      teamRecord.textContent = `Team Record: ${s.team_record || "N/A"}`;
    }

    if (oppRecord) {
      oppRecord.textContent = `Opp Record: ${s.opp_record || "N/A"}`;
    }

    if (oppStreak) {
      oppStreak.textContent = `Opp Streak: ${s.opp_streak || "N/A"}`;
    }

    if (consLine) {
      const avgCons =
        ((s.cons_pts ?? 0.5) +
          (s.cons_reb ?? 0.5) +
          (s.cons_ast ?? 0.5)) /
        3;
      const consPct = Math.round(avgCons * 100);
      consLine.innerHTML = `Profile · Consistency: <strong>${consPct}%</strong>`;
    }

    panel.appendChild(clone);
  });
}

// Helper: fill trend bars / arrows
function fillTrend(clone, label, seasonVal, last5Val, trend, cons, maxCeiling) {
  const bar = clone.querySelector(`.trend${label}Fill`);
  const valSpan = clone.querySelector(`.trendValue${label}`);
  const arrowSpan = clone.querySelector(`.trendArrow${label}`);

  const pct = Math.min(100, (last5Val / (maxCeiling || 1)) * 100);

  if (bar) bar.style.width = `${pct}%`;
  if (valSpan)
    valSpan.textContent = `${last5Val.toFixed(1)} (${seasonVal.toFixed(1)})`;

  let arrow = "■";
  if (trend === "up") arrow = "▲";
  else if (trend === "down") arrow = "▼";

  if (arrowSpan) arrowSpan.textContent = arrow;
}

// Filter buttons
document.querySelectorAll(".filterButton").forEach(btn => {
  btn.addEventListener("click", () => {
    currentFilter = btn.dataset.filter;
    document
      .querySelectorAll(".filterButton")
      .forEach(b => b.classList.remove("pill-active"));
    btn.classList.add("pill-active");
    renderProps();
  });
});

// View toggle
document.querySelectorAll(".viewBtn").forEach(btn => {
  btn.addEventListener("click", () => {
    currentView = btn.dataset.view;
    document
      .querySelectorAll(".viewBtn")
      .forEach(b => b.classList.remove("viewBtn-active"));
    btn.classList.add("viewBtn-active");
    renderProps();
  });
});

// Load button
document.getElementById("loadButton").addEventListener("click", loadData);
