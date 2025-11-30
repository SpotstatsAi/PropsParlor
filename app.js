// --------------------------------------------------
// Global state
// --------------------------------------------------
let rostersData = {};
let scheduleData = {};
let playerStats = {};
let lastProps = [];
let currentFilter = "all";
let selectedGame = null;

// --------------------------------------------------
// Data loading
// --------------------------------------------------
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
    updateScoreSummary(null);
  } catch (err) {
    console.error("Error loading data:", err);
    alert("Failed loading engine data.");
  }
}

// --------------------------------------------------
// Left side: Games & Teams
// --------------------------------------------------
function renderGames() {
  const gamesDiv = document.getElementById("games");
  gamesDiv.innerHTML = "";

  const today = new Date().toISOString().split("T")[0];
  const games = scheduleData[today] || [];

  if (!games.length) {
    gamesDiv.innerHTML = `<p class="emptyState">No games today.</p>`;
    updateScoreSummary(null);
    lastProps = [];
    renderProps();
    return;
  }

  games.forEach(game => {
    const card = document.createElement("div");
    card.className = "gameCard";

    card.innerHTML = `
      <strong>${game.away_team} @ ${game.home_team}</strong>
      <div>${game.time_et}</div>
    `;

    card.addEventListener("click", () => {
      selectedGame = game;
      highlightSelectedGame(card);
      showGameProps(game);
      updateScoreSummary(game);
    });

    gamesDiv.appendChild(card);
  });
}

function highlightSelectedGame(activeCard) {
  document
    .querySelectorAll(".gameCard")
    .forEach(card => card.classList.remove("activeGame"));
  activeCard.classList.add("activeGame");
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

// --------------------------------------------------
// Header scoreboard summary
// --------------------------------------------------
function updateScoreSummary(game) {
  const box = document.getElementById("scoreSummary");
  if (!box) return;

  if (!game) {
    box.textContent = "Select a game to see matchup summary.";
    return;
  }

  box.textContent = `${game.away_team} @ ${game.home_team} · ${game.time_et}`;
}

// --------------------------------------------------
// Click handlers
// --------------------------------------------------
function showTeamPlayers(team) {
  const panel = document.getElementById("propsOutput");
  panel.innerHTML = `<h3 class="panelTitle">${team} Roster</h3>`;

  (rostersData[team] || []).forEach(name => {
    const div = document.createElement("div");
    div.className = "rosterLine";
    div.textContent = name;
    panel.appendChild(div);
  });

  lastProps = [];
}

function showGameProps(game) {
  const awayPlayers = rostersData[game.away_team] || [];
  const homePlayers = rostersData[game.home_team] || [];

  const entries = [];
  awayPlayers.forEach(name => entries.push(buildProp(name)));
  homePlayers.forEach(name => entries.push(buildProp(name)));

  lastProps = entries;
  renderProps();
}

// --------------------------------------------------
// Build one player prop object
// --------------------------------------------------
function buildProp(name) {
  const stats = playerStats[name] || {};

  const score = scorePlayer(stats);
  let tier = "RED";
  if (score >= 0.75) tier = "GREEN";
  else if (score >= 0.55) tier = "YELLOW";

  return {
    name,
    stats,
    tier,
    score
  };
}

// Green / Yellow / Red scoring logic
function scorePlayer(s) {
  if (!s || !s.pts) return 0.45;

  let sc = 0.5;

  if (s.usage > 24) sc += 0.12;
  else if (s.usage > 20) sc += 0.06;

  if (s.min > 32) sc += 0.12;
  else if (s.min > 26) sc += 0.06;

  if (s.def_rank && s.def_rank <= 10) sc += 0.08;
  if (s.def_rank && s.def_rank >= 22) sc -= 0.06;

  // Nudge with trend vs season if we have last5
  const last5Pts = Array.isArray(s.trend_pts) && s.trend_pts.length
    ? avg(s.trend_pts)
    : null;

  if (last5Pts !== null) {
    const delta = last5Pts - s.pts;
    if (delta > 2.0) sc += 0.06;
    else if (delta < -2.0) sc -= 0.06;
  }

  return Math.max(0, Math.min(1, sc));
}

function avg(arr) {
  if (!arr || !arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

// --------------------------------------------------
// Render all player cards
// --------------------------------------------------
function renderProps() {
  const panel = document.getElementById("propsOutput");
  const template = document.getElementById("propRowTemplate");

  panel.innerHTML = "";
  if (!template) return;

  const filtered = lastProps.filter(p => {
    if (currentFilter === "all") return true;
    return p.tier === currentFilter.toUpperCase();
  });

  filtered.sort((a, b) => b.score - a.score);

  filtered.forEach(p => {
    const clone = document.importNode(template.content, true);
    const s = p.stats || {};

    // --- Header ---
    clone.querySelector(".propName").textContent = p.name;
    clone.querySelector(".propTeam").textContent = s.team || "";

    const tierEl = clone.querySelector(".tierTag");
    if (tierEl) {
      tierEl.textContent = p.tier;
      tierEl.classList.remove("tier-green", "tier-yellow", "tier-red");
      if (p.tier === "GREEN") tierEl.classList.add("tier-green");
      else if (p.tier === "YELLOW") tierEl.classList.add("tier-yellow");
      else tierEl.classList.add("tier-red");
    }

    // --- Meta badges: role / usage / pace ---
    const posBadge = clone.querySelector(".posBadge");
    const usgBadge = clone.querySelector(".usgBadge");
    const paceBadge = clone.querySelector(".paceBadge");

    const minutes = s.min ?? 0;
    const usage = s.usage ?? 0;
    const pace = s.pace ?? null;

    if (posBadge) {
      if (minutes >= 32) posBadge.textContent = "High-min starter";
      else if (minutes >= 24) posBadge.textContent = "Core rotation";
      else posBadge.textContent = "Bench / spot minutes";
    }

    if (usgBadge) {
      usgBadge.textContent = `USG ${usage.toFixed(1)}%`;
    }

    if (paceBadge) {
      if (pace == null) {
        paceBadge.textContent = "Pace: N/A";
      } else if (pace >= 102) {
        paceBadge.textContent = "Fast pace";
      } else if (pace <= 98) {
        paceBadge.textContent = "Slow pace";
      } else {
        paceBadge.textContent = "Average pace";
      }
    }

    // --- Matchup section ---
    const opp = s.opponent;
    const oppLineEl = clone.querySelector(".oppLine");
    const oppRankEl = clone.querySelector(".oppRank");
    const oppStreakEl = clone.querySelector(".oppStreak");

    if (oppLineEl) {
      oppLineEl.textContent = opp ? `${s.team} vs ${opp}` : "No game today";
    }

    if (oppRankEl) {
      oppRankEl.textContent = s.def_rank
        ? `Defense rank: #${s.def_rank}`
        : "Defense rank: N/A";
    }

    if (oppStreakEl) {
      oppStreakEl.textContent = s.opp_streak
        ? `Opp streak: ${s.opp_streak}`
        : "Opp streak: N/A";
    }

    // --- Season averages ---
    const pts = s.pts ?? 0;
    const reb = s.reb ?? 0;
    const ast = s.ast ?? 0;

    const avgPtsEl = clone.querySelector(".avgPts");
    const avgRebEl = clone.querySelector(".avgReb");
    const avgAstEl = clone.querySelector(".avgAst");

    if (avgPtsEl) avgPtsEl.textContent = pts.toFixed(1);
    if (avgRebEl) avgRebEl.textContent = reb.toFixed(1);
    if (avgAstEl) avgAstEl.textContent = ast.toFixed(1);

    // Trend bars vs reasonable ceilings (40 / 15 / 12)
    const ptsPct = Math.min(100, (pts / 40) * 100);
    const rebPct = Math.min(100, (reb / 15) * 100);
    const astPct = Math.min(100, (ast / 12) * 100);

    const ptsFill = clone.querySelector(".trendPtsFill");
    const rebFill = clone.querySelector(".trendRebFill");
    const astFill = clone.querySelector(".trendAstFill");

    if (ptsFill) ptsFill.style.width = ptsPct + "%";
    if (rebFill) rebFill.style.width = rebPct + "%";
    if (astFill) astFill.style.width = astPct + "%";

    // --- Team context ---
    const teamRecordEl = clone.querySelector(".teamRecord");
    const oppRecordEl = clone.querySelector(".oppRecord");

    if (teamRecordEl) {
      teamRecordEl.textContent = s.team_record || "N/A";
    }
    if (oppRecordEl) {
      oppRecordEl.textContent = s.opp_record || "N/A";
    }

    // --- Trend note badges from rolling windows ---
    const volBadge = clone.querySelector(".volBadge");
    const hotColdBadge = clone.querySelector(".hotColdBadge");

    const last5 = Array.isArray(s.trend_pts) && s.trend_pts.length
      ? avg(s.trend_pts)
      : null;
    const last10 = Array.isArray(s.ten_game_pts) && s.ten_game_pts.length
      ? avg(s.ten_game_pts)
      : null;

    if (volBadge) {
      if (last10 !== null && last10 > pts + 1.5) {
        volBadge.textContent = "Volume trending up";
      } else if (last10 !== null && last10 < pts - 1.5) {
        volBadge.textContent = "Usage cooling off";
      } else {
        volBadge.textContent = "Volume stable";
      }
    }

    if (hotColdBadge) {
      if (last5 !== null) {
        const delta = last5 - pts;
        if (delta > 2) hotColdBadge.textContent = "HOT last 5";
        else if (delta < -2) hotColdBadge.textContent = "COLD last 5";
        else hotColdBadge.textContent = "Neutral last 5";
      } else {
        hotColdBadge.textContent = "No trend data";
      }
    }

    panel.appendChild(clone);
  });

  if (!filtered.length) {
    panel.innerHTML = `<p class="emptyState">No players match this filter.</p>`;
  }
}

// --------------------------------------------------
// Filter buttons (All / Green / Yellow / Red)
// --------------------------------------------------
document.querySelectorAll(".filterButton").forEach(btn => {
  btn.addEventListener("click", () => {
    currentFilter = btn.dataset.filter;

    document
      .querySelectorAll(".filterButton")
      .forEach(b => b.classList.remove("filterActive"));

    btn.classList.add("filterActive");
    renderProps();
  });
});

// --------------------------------------------------
// View mode toggle (Expanded / Compact)
// --------------------------------------------------
const viewToggleButtons = document.querySelectorAll(".toggleButton");

viewToggleButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    viewToggleButtons.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    const mode = btn.dataset.mode;
    if (mode === "compact") {
      document.body.classList.add("compactMode");
    } else {
      document.body.classList.remove("compactMode");
    }
  });
});

// --------------------------------------------------
// Hook up Load button
// --------------------------------------------------
document.getElementById("loadButton").addEventListener("click", loadData);
