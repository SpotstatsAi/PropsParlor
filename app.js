let rostersData = {};
let scheduleData = {};
let playerStats = {};
let lastProps = [];
let currentFilter = "all";

async function loadData() {
  try {
    const rostersURL = "rosters.json";
    const scheduleURL = "schedule.json";
    const statsURL = "player_stats.json";

    const [rosters, schedule, stats] = await Promise.all([
      fetch(rostersURL).then(r => r.json()),
      fetch(scheduleURL).then(r => r.json()),
      fetch(statsURL).then(r => r.json())
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

  const entries = [];
  awayPlayers.forEach(n => entries.push(buildProp(n)));
  homePlayers.forEach(n => entries.push(buildProp(n)));

  lastProps = entries;
  renderProps();
}

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

    clone.querySelector(".propName").textContent = p.name;
    clone.querySelector(".propTeam").textContent = `Team: ${p.stats.team}`;

    clone.querySelector(".oppLine").textContent =
      `Opponent: ${p.stats.opponent || "N/A"}`;

    clone.querySelector(".oppRank").textContent =
      `Def Rank: ${p.stats.def_rank || "N/A"}`;

    // Season Averages
clone.querySelector(".avgPts").textContent =
  `PTS: ${p.stats.pts?.toFixed(1) || 0}`;

clone.querySelector(".avgReb").textContent =
  `REB: ${p.stats.reb?.toFixed(1) || 0}`;

clone.querySelector(".avgAst").textContent =
  `AST: ${p.stats.ast?.toFixed(1) || 0}`;

// Advanced
clone.querySelector(".usageLine").textContent =
  `Usage: ${p.stats.usage?.toFixed(1) || 0}%`;

clone.querySelector(".paceLine").textContent =
  `Pace: ${p.stats.pace || "N/A"}`;


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

.seasonAverages {
  width: 22%;
  font-size: 0.85em;
  opacity: 0.9;
}

.seasonAverages div {
  line-height: 1.3em;
}
