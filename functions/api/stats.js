// functions/api/stats.js
//
// Generic stats endpoint backed by player_stats.json
//
// Usage examples:
//   /api/stats
//   /api/stats?player_id=237
//   /api/stats?team=LAL
//   /api/stats?date_from=2025-01-01&date_to=2025-01-31
//   /api/stats?player_id=237&last_n=10&sort=date-desc
//
// Notes:
// - Assumes player_stats.json contains an array somewhere; we try to
//   detect it via extractRowsFromStatsPayload.

export async function onRequest(context) {
  const { request } = context;

  if (request.method !== "GET") {
    return jsonResponse({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    const url = new URL(request.url);
    const sp = url.searchParams;

    const filters = {
      playerId: sp.get("player_id") ? String(sp.get("player_id")).trim() : "",
      team: sp.get("team")
        ? String(sp.get("team")).trim().toUpperCase()
        : "",
      dateFrom: sp.get("date_from") ? String(sp.get("date_from")).trim() : "",
      dateTo: sp.get("date_to") ? String(sp.get("date_to")).trim() : "",
      lastN: sp.get("last_n") ? parseInt(sp.get("last_n"), 10) || null : null,
      sort: sp.get("sort") || "date-desc", // date-desc | date-asc | stat-pts-desc | stat-pts-asc
    };

    const statsUrl = new URL("/player_stats.json", url);
    const statsRes = await fetch(statsUrl.toString(), {
      cf: { cacheTtl: 60, cacheEverything: true },
    });

    if (!statsRes.ok) {
      throw new Error(
        `Failed to load player_stats.json (HTTP ${statsRes.status})`
      );
    }

    const raw = await statsRes.json();
    const rowsRaw = extractRowsFromStatsPayload(raw);
    const rows = rowsRaw.map(normalizeRow).filter((r) => !!r);

    let filtered = applyFilters(rows, filters);

    // Apply last_n AFTER filters/date range (keeping most recent first)
    if (filters.lastN && filters.lastN > 0) {
      filtered = filtered
        .sort((a, b) => (b.gameDate || "").localeCompare(a.gameDate || ""))
        .slice(0, filters.lastN);
    }

    filtered = applySort(filtered, filters.sort);

    const meta = buildMeta(rows, filtered, filters);

    return jsonResponse(
      {
        data: filtered,
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
    console.error("api/stats error:", err);

    return jsonResponse({ error: "Failed to load stats." }, { status: 500 });
  }
}

/* ---------- helpers ---------- */

function jsonResponse(body, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("content-type", "application/json; charset=utf-8");
  return new Response(JSON.stringify(body, null, 2), { ...options, headers });
}

// Try to find the actual array of stat rows inside an arbitrary JSON payload.
function extractRowsFromStatsPayload(raw) {
  if (!raw) return [];

  if (Array.isArray(raw)) return raw;

  if (Array.isArray(raw.data)) return raw.data;

  // Fallback: first array-valued property.
  if (typeof raw === "object") {
    for (const value of Object.values(raw)) {
      if (Array.isArray(value)) return value;
    }
  }

  return [];
}

function parseDateFromRow(row) {
  const candidates = ["game_date", "date", "day", "dt"];
  for (const key of candidates) {
    if (row[key]) {
      const raw = String(row[key]);
      if (raw.length >= 10 && /^\d{4}-\d{2}-\d{2}/.test(raw)) {
        return raw.slice(0, 10);
      }
    }
  }
  return null;
}

function normalizeRow(raw) {
  if (!raw) return null;

  const playerId =
    raw.player_id ||
    (raw.player && raw.player.id) ||
    raw.id ||
    null;

  const firstName =
    (raw.player && (raw.player.first_name || raw.player.firstName)) ||
    raw.first_name ||
    raw.firstName ||
    "";
  const lastName =
    (raw.player && (raw.player.last_name || raw.player.lastName)) ||
    raw.last_name ||
    raw.lastName ||
    "";

  const name = raw.player_name || `${firstName} ${lastName}`.trim();

  const teamAbbr =
    raw.team ||
    raw.team_abbr ||
    (raw.team && raw.team.abbreviation) ||
    raw.team_abbreviation ||
    "";

  const gameDate = parseDateFromRow(raw);

  const stats = {
    pts: numberOrNull(raw.pts ?? raw.points),
    reb: numberOrNull(raw.reb ?? raw.rebounds),
    ast: numberOrNull(raw.ast ?? raw.assists),
    stl: numberOrNull(raw.stl ?? raw.steals),
    blk: numberOrNull(raw.blk ?? raw.blocks),
    fg3m: numberOrNull(raw.fg3m ?? raw.threes_made),
    min: raw.min || raw.minutes || null,
  };

  return {
    playerId: playerId != null ? String(playerId) : null,
    name,
    firstName,
    lastName,
    team: teamAbbr ? String(teamAbbr).toUpperCase() : "",
    gameDate,
    raw,
    stats,
  };
}

function numberOrNull(v) {
  if (v === undefined || v === null || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

function applyFilters(rows, filters) {
  const { playerId, team, dateFrom, dateTo } = filters;
  let out = rows.slice();

  if (playerId) {
    out = out.filter((r) => r.playerId === playerId);
  }

  if (team) {
    out = out.filter((r) => r.team === team);
  }

  if (dateFrom) {
    out = out.filter(
      (r) => !r.gameDate || r.gameDate >= dateFrom
    );
  }

  if (dateTo) {
    out = out.filter(
      (r) => !r.gameDate || r.gameDate <= dateTo
    );
  }

  return out;
}

function applySort(rows, sortKey) {
  const list = rows.slice();

  switch (sortKey) {
    case "date-asc":
      list.sort((a, b) => (a.gameDate || "").localeCompare(b.gameDate || ""));
      break;
    case "stat-pts-asc":
      list.sort(
        (a, b) =>
          (a.stats.pts ?? -1) - (b.stats.pts ?? -1)
      );
      break;
    case "stat-pts-desc":
      list.sort(
        (a, b) =>
          (b.stats.pts ?? -1) - (a.stats.pts ?? -1)
      );
      break;
    case "date-desc":
    default:
      list.sort((a, b) => (b.gameDate || "").localeCompare(a.gameDate || ""));
      break;
  }

  return list;
}

function buildMeta(allRows, filteredRows, filters) {
  const uniquePlayers = new Set(
    allRows.map((r) => r.playerId).filter(Boolean)
  );
  const uniqueTeams = new Set(allRows.map((r) => r.team).filter(Boolean));

  return {
    totalRows: allRows.length,
    filteredRows: filteredRows.length,
    uniquePlayers: uniquePlayers.size,
    uniqueTeams: uniqueTeams.size,
    filters: {
      playerId: filters.playerId || "",
      team: filters.team || "",
      dateFrom: filters.dateFrom || "",
      dateTo: filters.dateTo || "",
      lastN: filters.lastN || null,
      sort: filters.sort || "date-desc",
    },
    source: "player_stats.json",
  };
}
