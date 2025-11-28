// scripts/build_player_stats.mjs

import fs from "fs/promises";

// --- CONFIG ----------------------------------------------------

const OWNER = "SpotstatsAi";
const REPO  = "SpotstatsAi";
const BRANCH = "main"; // change if your default branch is not main

const ROSTERS_URL  =
  `https://raw.githubusercontent.com/${OWNER}/${REPO}/${BRANCH}/rosters.json`;
const SCHEDULE_URL =
  `https://raw.githubusercontent.com/${OWNER}/${REPO}/${BRANCH}/schedule.json`;

// Output files (in repo root)
const OUTPUT_STATS_FILE = "player_stats.json";
const OUTPUT_DEBUG_FILE = "player_stats_debug.json";

// --- UTILS -----------------------------------------------------

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url}: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

function todayYMD() {
  const d = new Date();
  // Force to UTC date; Github runner is UTC
  const year  = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day   = String(d.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function yesterdayYMD() {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 1);
  const year  = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day   = String(d.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

// --- BACK-TO-BACK FROM SCHEDULE.JSON ---------------------------

function computeBackToBackTeams(scheduleData) {
  const today = todayYMD();
  const yesterday = yesterdayYMD();

  const todaysGames = scheduleData[today] || [];
  const yesterdaysGames = scheduleData[yesterday] || [];

  const teamsToday = new Set();
  const teamsYesterday = new Set();

  for (const g of todaysGames) {
    if (g.home_team) teamsToday.add(g.home_team);
    if (g.away_team) teamsToday.add(g.away_team);
  }
  for (const g of yesterdaysGames) {
    if (g.home_team) teamsYesterday.add(g.home_team);
    if (g.away_team) teamsYesterday.add(g.away_team);
  }

  const backToBackTeams = new Set();
  for (const t of teamsToday) {
    if (teamsYesterday.has(t)) {
      backToBackTeams.add(t);
    }
  }
  return backToBackTeams;
}

// --- PLACEHOLDER STATS ENGINE ---------------------------------
// This keeps everything deterministic and structured until
// you plug in a real API / data source.

function makePlaceholderStats(playerName, teamAbbr, isBackToBack) {
  // deterministic code from player name + team
  const key = playerName + "|" + teamAbbr;
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }

  // minutes: 22–36
  const minutes = 22 + (hash % 15);        // 22..36

  // usage: 17–30%
  const usage = 17 + (hash % 14);          // 17..30

  // hitRate: 0.40–0.72
  const hitBase = 40 + (hash % 33);        // 40..72
  const hitRate = hitBase / 100;

  return {
    minutes,
    usage,
    hitRate,
    backToBack: isBackToBack
  };
}

// NOTE: when you pick a real data provider, replace this
// with a function that calls that API and returns the same shape.
async function fetchRealStatsOrPlaceholder(playerName, teamAbbr, isBackToBack) {
  // TODO: plug in real data source here later.
  return makePlaceholderStats(playerName, teamAbbr, isBackToBack);
}

// --- MAIN BUILD LOGIC -----------------------------------------

async function buildPlayerStats() {
  console.log("[STATS] Fetching rosters and schedule...");

  const [rosters, schedule] = await Promise.all([
    fetchJSON(ROSTERS_URL),
    fetchJSON(SCHEDULE_URL)
  ]);

  const backToBackTeams = computeBackToBackTeams(schedule);

  const playerStats = {};
  const debug = {
    generatedAt: new Date().toISOString(),
    today: todayYMD(),
    yesterday: yesterdayYMD(),
    totalTeams: 0,
    totalPlayers: 0,
    backToBackTeams: Array.from(backToBackTeams),
    errors: []
  };

  let teamCount = 0;
  let playerCount = 0;

  for (const [teamAbbr, players] of Object.entries(rosters)) {
    teamCount++;
    const isTeamB2B = backToBackTeams.has(teamAbbr);

    if (!Array.isArray(players)) continue;

    for (const playerName of players) {
      playerCount++;
      try {
        const stats = await fetchRealStatsOrPlaceholder(
          playerName,
          teamAbbr,
          isTeamB2B
        );

        // Keyed exactly by name, which is what your app.js expects
        playerStats[playerName] = stats;
      } catch (err) {
        console.error(`[STATS] Failed for ${playerName} (${teamAbbr}):`, err);
        debug.errors.push({
          player: playerName,
          team: teamAbbr,
          message: String(err)
        });
      }
    }
  }

  debug.totalTeams = teamCount;
  debug.totalPlayers = playerCount;

  console.log(`[STATS] Built stats for ${playerCount} players across ${teamCount} teams.`);
  console.log(`[STATS] Writing ${OUTPUT_STATS_FILE} and ${OUTPUT_DEBUG_FILE}...`);

  await fs.writeFile(
    OUTPUT_STATS_FILE,
    JSON.stringify(playerStats, null, 2),
    "utf8"
  );

  await fs.writeFile(
    OUTPUT_DEBUG_FILE,
    JSON.stringify(debug, null, 2),
    "utf8"
  );

  console.log("[STATS] Done.");
}

// --- RUN -------------------------------------------------------

buildPlayerStats().catch(err => {
  console.error("[STATS] Fatal error:", err);
  process.exit(1);
});
