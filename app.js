// YOUR DATA SOURCES
const ROSTERS_URL = "/rosters.json";
const PLAYER_STATS_URL = "/player_stats.json";
const SCHEDULE_URL = "/schedule.json";

// LIVE BDL OVERRIDE
const BDL_BASE = "https://api.balldontlie.io/v1";
const BDL_KEY = "YOUR_BDL_KEY_HERE"; // <––– INSERT SECRET WHEN USING SERVER-SIDE ONLY

//-------------------------------------------------------
// MAIN LOAD
//-------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
    showSection("players-section");

    const [rosters, stats, schedule] = await Promise.all([
        fetch(ROSTERS_URL).then(r => r.json()),
        fetch(PLAYER_STATS_URL).then(r => r.json()),
        fetch(SCHEDULE_URL).then(r => r.json()),
    ]);

    window.ROSTERS = rosters;
    window.STATS = stats;
    window.SCHEDULE = schedule;

    renderPlayers(stats);
    renderTeams(rosters);
    renderGames(schedule);
    renderTrending(stats);
});

//-------------------------------------------------------
// NAVIGATION
//-------------------------------------------------------
function showSection(id) {
    document.querySelectorAll(".page-section").forEach(s => {
        s.classList.remove("visible");
    });
    document.getElementById(id).classList.add("visible");
}

//-------------------------------------------------------
// PLAYERS
//-------------------------------------------------------
function renderPlayers(stats) {
    const grid = document.getElementById("players-grid");
    grid.innerHTML = "";

    stats.forEach(p => {
        const card = document.createElement("div");
        card.className = "card";

        card.innerHTML = `
            <h2>${p.player_name}</h2>
            <div class="small">${p.team_abbreviation}</div>
            <div class="small">PPG: ${p.points}</div>
            <div class="small">APG: ${p.assists}</div>
            <div class="small">RPG: ${p.rebounds}</div>
        `;

        grid.appendChild(card);
    });
}

//-------------------------------------------------------
// TEAMS
//-------------------------------------------------------
function renderTeams(rosters) {
    const grid = document.getElementById("teams-grid");
    grid.innerHTML = "";

    const teams = {};

    rosters.forEach(p => {
        if (!teams[p.team_abbreviation]) {
            teams[p.team_abbreviation] = [];
        }
        teams[p.team_abbreviation].push(p.player_name);
    });

    Object.keys(teams).forEach(team => {
        const card = document.createElement("div");
        card.className = "card";

        card.innerHTML = `
            <h2>${team}</h2>
            <div class="small">${teams[team].length} players</div>
        `;

        grid.appendChild(card);
    });
}

//-------------------------------------------------------
// GAMES
//-------------------------------------------------------
function renderGames(schedule) {
    const today = new Date().toISOString().split("T")[0];
    const games = schedule.filter(g => g.game_date === today);

    const list = document.getElementById("games-list");
    list.innerHTML = "";

    if (games.length === 0) {
        list.innerHTML = `<div class="small">No games today.</div>`;
        return;
    }

    games.forEach(g => {
        const card = document.createElement("div");
        card.className = "game-card";

        card.innerHTML = `
            <div class="teams">${g.away_team_abbr} @ ${g.home_team_abbr}</div>
            <div class="time">${g.game_time || "TBD"}</div>
        `;

        list.appendChild(card);
    });
}

//-------------------------------------------------------
// TRENDING
//-------------------------------------------------------
function renderTrending(stats) {
    const grid = document.getElementById("trending-grid");
    grid.innerHTML = "";

    const top = [...stats]
        .sort((a, b) => b.points - a.points)
        .slice(0, 20);

    top.forEach(p => {
        const card = document.createElement("div");
        card.className = "card";

        card.innerHTML = `
            <h2>${p.player_name}</h2>
            <div class="small">${p.team_abbreviation}</div>
            <div class="small">PPG: ${p.points}</div>
        `;

        grid.appendChild(card);
    });
}
