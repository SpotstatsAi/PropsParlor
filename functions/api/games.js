// functions/api/games.js
//
// File-backed games endpoint using schedule.json at repo root.
//
// Usage examples:
//   /api/games                     -> games for "today" (UTC) if possible
//   /api/games?date=2025-12-05     -> games on that date
//   /api/games?team=LAL            -> games where LAL is home or away
//
// Because schedule.json schema can vary, this function:
//  - Tries multiple common fields for date and team abbreviations.
//  - If it cannot detect a date field, it returns the full schedule
//    and marks meta.dateFiltered = false.

export async function onRequest(context) {
  const { request } = context;

  if (request.method !== "GET") {
    return jsonResponse(
      { error: "Method not allowed" },
      { status: 405 }
    );
  }

  try {
    const url = new URL(request.url);
    const searchParams = url.searchParams;

    // Query params
    const dateParam = (searchParams.get("date") || "").trim(); // YYYY-MM-DD or empty
    const teamParam = (searchParams.get("team") || "").trim().toUpperCase(); // team abbreviation or empty

    // Determine target date (UTC yyyy-mm-dd) if not provided
    const effectiveDate = dateParam || utcToday();

    // Load schedule.json from repo root
    const scheduleUrl = new URL("/schedule.json", url);

    const scheduleRes = await fetch(scheduleUrl.toString(), {
      cf: { cacheTtl: 60, cacheEverything: true },
    });

    if (!scheduleRes.ok) {
      throw new Error(`Failed to load schedule.json (HTTP ${scheduleRes.status})`);
    }

    const raw = await scheduleRes.json();
    const games = Array.isArray(raw) ? raw : raw.games || [];

    if (!Array.isArray(games)) {
      return jsonResponse(
        { error: "schedule.json is not an array and has no 'games' array" },
        { status: 500 }
      );
    }

    const { filteredGames, dateFiltered, teamFiltered, usedDateField } =
      filterGames(games, effectiveDate, teamParam);

    const meta = buildMeta({
      allGames: games,
      filteredGames,
      effectiveDate,
      dateParam,
      teamParam,
      dateFiltered,
      teamFiltered,
      usedDateField,
    });

    return jsonResponse(
      {
        data: filteredGames,
        meta,
      },
      {
        status: 200,
        headers: {
          "cache-control": "public, max-age=30",
        },
      }
    );
  } catch (err) {
    console.error("api/games error:", err);

    return jsonResponse(
      { error: "Failed to load games." },
      { status: 500 }
    );
  }
}

/* ---------- helpers ---------- */

function jsonResponse(body, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("content-type", "application/json; charset=utf-8");

  return new Response(JSON.stringify(body, null, 2), {
    ...options,
    headers,
  });
}

// Returns "YYYY-MM-DD" in UTC
function utcToday() {
  const now = new Date();
  const y = now.getUTCFullYear();
  const m = String(now.getUTCMonth() + 1).padStart(2, "0");
  const d = String(now.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

// Try to pull a YYYY-MM-DD out of various common fields.
// Returns { dateStr, fieldName } where dateStr is e.g. "2025-12-05" or null.
function extractGameDate(game) {
  // Common patterns we might see
  const candidates = [
    "game_date",
    "date",
    "start_time",
    "tipoff",
    "start_time_utc",
  ];

  for (const field of candidates) {
    if (!game[field]) continue;
    const raw = String(game[field]);
    // if looks like ISO date/datetime, first 10 chars are yyyy-mm-dd
    if (raw.length >= 10 && /^\d{4}-\d{2}-\d{2}/.test(raw)) {
      return { dateStr: raw.slice(0, 10), fieldName: field };
    }
  }

  return { dateStr: null, fieldName: null };
}

// Try to find team abbreviations for home/away.
// Supports a few shapes but does not enforce a schema.
function extractTeamAbbrs(game) {
  let home = null;
  let away = null;

  // Flattened fields first
  home = game.home_team || game.home || game.home_abbr || null;
  away = game.away_team || game.away || game.away_abbr || null;

  // Nested objects with .abbreviation
  if (!home && game.home_team && typeof game.home_team === "object") {
    home = game.home_team.abbreviation || game.home_team.abbr || null;
  }
  if (!away && game.away_team && typeof game.away_team === "object") {
    away = game.away_team.abbreviation || game.away_team.abbr || null;
  }

  // Normalize to uppercase strings
  home = home ? String(home).toUpperCase() : null;
  away = away ? String(away).toUpperCase() : null;

  return { home, away };
}

function filterGames(allGames, targetDate, teamAbbr) {
  let usedDateField = null;
  let dateFiltered = false;
  let teamFiltered = false;

  // First pass: determine which date field we can reliably use, if any.
  // We scan until we find a game with a detectable date field.
  for (const g of allGames) {
    const { dateStr, fieldName } = extractGameDate(g);
    if (dateStr && fieldName) {
      usedDateField = fieldName;
      break;
    }
  }

  let games = allGames;

  if (usedDateField) {
    games = games.filter((g) => {
      const raw = String(g[usedDateField] || "");
      if (raw.length < 10) return false;
      const d = raw.slice(0, 10);
      return d === targetDate;
    });
    dateFiltered = true;
  }

  if (teamAbbr) {
    games = games.filter((g) => {
      const { home, away } = extractTeamAbbrs(g);
      return home === teamAbbr || away === teamAbbr;
    });
    teamFiltered = true;
  }

  return {
    filteredGames: games,
    dateFiltered,
    teamFiltered,
    usedDateField,
  };
}

function buildMeta({
  allGames,
  filteredGames,
  effectiveDate,
  dateParam,
  teamParam,
  dateFiltered,
  teamFiltered,
  usedDateField,
}) {
  const totalGames = allGames.length;
  const filteredCount = filteredGames.length;

  let homeTeams = new Set();
  let awayTeams = new Set();

  filteredGames.forEach((g) => {
    const { home, away } = extractTeamAbbrs(g);
    if (home) homeTeams.add(home);
    if (away) awayTeams.add(away);
  });

  return {
    totalGames,
    filteredGames: filteredCount,
    uniqueHomeTeams: homeTeams.size,
    uniqueAwayTeams: awayTeams.size,
    date: {
      requested: dateParam || null,
      effective: effectiveDate,
      filtered: dateFiltered,
      usedField: usedDateField,
    },
    filters: {
      team: teamParam || "",
      teamFiltered,
    },
    source: "schedule.json",
  };
}
