// functions/api/games.js
//
// Games endpoint backed by schedule.json
//
// Usage examples:
//   /api/games
//   /api/games?date=2025-12-05   (YYYY-MM-DD)
//
// Responds with normalized games:
//   {
//     data: [
//       {
//         id: "12345",
//         gameDate: "2025-12-05",
//         start_time_local: "2025-12-05T19:30:00",
//         home_team_abbr: "LAL",
//         away_team_abbr: "BOS",
//         raw: { ...original game row... }
//       },
//       ...
//     ],
//     meta: { ... }
//   }

export async function onRequest(context) {
  const { request } = context;

  if (request.method !== "GET") {
    return jsonResponse({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    const url = new URL(request.url);
    const sp = url.searchParams;
    const dateFilter = (sp.get("date") || "").trim(); // YYYY-MM-DD

    const schedUrl = new URL("/schedule.json", url);
    const schedRes = await fetch(schedUrl.toString(), {
      cf: { cacheTtl: 60, cacheEverything: true },
    });

    if (!schedRes.ok) {
      throw new Error(
        `Failed to load schedule.json (HTTP ${schedRes.status})`
      );
    }

    const raw = await schedRes.json();
    const rowsRaw = extractGamesArray(raw);
    const rows = rowsRaw.map(normalizeGame).filter(Boolean);

    let filtered = rows;

    if (dateFilter) {
      filtered = filtered.filter((g) => g.gameDate === dateFilter);
    }

    const meta = {
      totalGames: rows.length,
      filteredGames: filtered.length,
      date: dateFilter || null,
      source: "schedule.json",
    };

    return jsonResponse(
      { data: filtered, meta },
      {
        status: 200,
        headers: {
          "cache-control": "public, max-age=60",
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
  return new Response(JSON.stringify(body, null, 2), { ...options, headers });
}

// Try to find the array of games in schedule.json
function extractGamesArray(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw.games)) return raw.games;
  if (Array.isArray(raw.data)) return raw.data;
  if (typeof raw === "object") {
    for (const value of Object.values(raw)) {
      if (Array.isArray(value)) return value;
    }
  }
  return [];
}

function normalizeGame(row) {
  if (!row || typeof row !== "object") return null;

  const id =
    row.game_id ||
    row.id ||
    row.bdl_id ||
    null;

  // Date: prefer explicit game_date or date; fall back to first 10 chars of start time
  let gameDate =
    (row.game_date && String(row.game_date).slice(0, 10)) ||
    (row.date && String(row.date).slice(0, 10)) ||
    null;

  const startTime =
    row.start_time_local ||
    row.start_time ||
    row.tipoff_local ||
    row.tipoff ||
    null;

  if (!gameDate && startTime && String(startTime).length >= 10) {
    gameDate = String(startTime).slice(0, 10);
  }

  const home =
    row.home_team_abbr ||
    (row.home_team && row.home_team.abbreviation) ||
    row.home_team ||
    row.home ||
    null;

  const away =
    row.away_team_abbr ||
    (row.away_team && row.away_team.abbreviation) ||
    row.away_team ||
    row.away ||
    null;

  return {
    id: id != null ? String(id) : null,
    gameDate: gameDate || null,
    start_time_local: startTime || null,
    home_team_abbr: home ? String(home).toUpperCase() : null,
    away_team_abbr: away ? String(away).toUpperCase() : null,
    raw: row,
  };
}
