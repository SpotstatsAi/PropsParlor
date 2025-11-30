let rostersData = {};
let scheduleData = {};
let playerStats = {};
let lastProps = [];
let currentFilter = "all";

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

function showTeamPlayers(team) {
  const panel = document.getElementById("propsOutput");
  panel.innerHTML = `<h3>${team} Roster</h3>`;

  rostersData[team].forEach(name => {
    panel.innerHTML += `<div class="propRow"><span>${name}</span></div>`;
  });

  lastProps = [];
}

function showGameProps(game) {
  const awayPlayers = rostersData[game.away_team] || [];
  const homePlayers = rostersData[game.home_team] || [];

  const entries = [
    ...awayPlayers.map(n => buildProp(n)),
    ...homePlayers.map(n => buildProp(n))
  ];

  lastProps = entries;
  renderProps();
}

function buildProp(name) {
  const stats = playerStats[name] || {};
  const score = scorePlayer(stats);

  let tier = "RED";
  if (score >= 0.75) tier = "GREEN";
  else if (score >= 0.55) tier = "YELLOW";

  return { name, stats, tier, score };
}

function scorePlayer(s) {
  if (!s || !s.pts) return 0.45;

  let sc = 0.5;

  if (s.usage > 22) sc += 0.1;
  if (s.min > 28) sc += 0.1;
  if (s.def_rank <= 10) sc += 0.1;
  if (s.def_rank >= 20) sc -= 0.1;

  return Math.max(0, Math.min(1, sc));
}

function renderProps() {
  const panel = document.getElementById("propsOutput");
  const template = document.getElementById("propRowTemplate");

  panel.innerHTML = "";

  const filtered = lastProps.filter(p => {
    if (currentFilter === "all") return true;
    return p.tier === currentFilter.toUpperCase();
  });

  filtered.sort((a, b) => b.score - a.score);

  filtered.forEach(p => {
    const clone = document.importNode(template.content, true);

    // Main names
    clone.querySelector(".propName").textContent = p.name;
    clone.querySelector(".propTeam").textContent = `${p.stats.team}`;

    // Opponent + Rank
    clone.querySelector(".oppLine").textContent =
      p.stats.opponent ? `${p.stats.team} vs ${p.stats.opponent}` : "No game";

    clone.querySelector(".oppRank").textContent =
      p.stats.def_rank ? `Defense Rank: ${p.stats.def_rank}` : "";

    // Season Averages
    clone.querySelector(".avgPts").textContent = `PTS: ${p.stats.pts?.toFixed(1)}`;
    clone.querySelector(".avgReb").textContent = `REB: ${p.stats.reb?.toFixed(1)}`;
    clone.querySelector(".avgAst").textContent = `AST: ${p.stats.ast?.toFixed(1)}`;

    // Advanced
    clone.querySelector(".usageLine").textContent =
      `USG: ${p.stats.usage?.toFixed(1)}%`;

    clone.querySelector(".paceLine").textContent =
      `Pace: ${p.stats.pace ?? "N/A"}`;

    // Records
    clone.querySelector(".teamRecord").textContent =
      p.stats.team_record || "N/A";

    clone.querySelector(".oppRecord").textContent =
      p.stats.opp_record || "N/A";

    clone.querySelector(".oppStreak").textContent =
      `Streak: ${p.stats.opp_streak || "N/A"}`;

    // Tier color
    const tag = clone.querySelector(".tierTag");
    tag.textContent = p.tier;

    if (p.tier === "GREEN") tag.classList.add("tier-green");
    else if (p.tier === "YELLOW") tag.classList.add("tier-yellow");
    else tag.classList.add("tier-red");

    panel.appendChild(clone);
  });
}

// Filters
document.querySelectorAll(".filterButton").forEach(btn => {
  btn.onclick = () => {
    currentFilter = btn.dataset.filter;
    document.querySelectorAll(".filterButton").forEach(b => b.classList.remove("filterActive"));
    btn.classList.add("filterActive");
    renderProps();
  };
});

document.getElementById("loadButton").onclick = loadData;
