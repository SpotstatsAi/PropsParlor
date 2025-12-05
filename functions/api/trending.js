// functions/api/trending.js
//
// Trending players endpoint using player_stats.json + rosters.json.
//
// For each player, looks at their most recent N games and computes an
// average of a chosen stat (pts by default), then ranks descending.
//
// Usage examples:
//   /api/trending
//   /api/trending?stat=pts&last_n=5&min_games=3&limit=50
//   /api/trending?team=LAL
//   /api/trending?position=G

export async function onRequest(context) {
  const { request } = context;

  if (request.method !== "GET") {
    return jsonResponse({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    const url = new URL(request.url);
    const sp = url.searchParams;

    const stat = (sp.get("stat") || "pts").toLowerCase();
    const lastN = sp.get("last_n")
      ? clampInt(sp.get("last_n"), 2, 20)
      : 5;
    const minGames = sp.get("min_games")
      ? clampInt(sp.get("min_games"), 2, lastN)
      : 3;
    const limit = sp.get("limit")
      ? clampInt(sp.get("limit"), 1, 200)
      : 50;

    const teamFilter = sp.get("team")
      ? String(sp.get("team")).trim().toUpperCase()
      : "";
    const posFilter = sp.get("position")
      ? String(sp.get("position")).trim().toUpperCase()
      : "";

    // Load stats
    const statsUrl = new URL("/player_stats.json", url);
    const statsRes = await fetch(statsUrl.toString(), {
      cf: { cacheTtl: 60, cacheEverything: true },
    });
    if (!statsRes.ok) {
      throw new Error(
        `Failed to load player_stats.json (HTTP ${statsRes.status})`
      );
    }
    const statsRaw = await statsRes.json();
    const rowsRaw = extractRowsFromStatsPayload(statsRaw);
    const rows = rowsRaw.map(normalizeRow).filter((r) => !!r);

    // Load rosters for position + official team if present
    const rosters = await loadRosters(url);
    const rosterIndex = buildRosterIndex(rosters);

    const byPlayer = groupByPlayer(rows);

    const trending = [];

    for (const [playerId, entries] of byPlayer.entries()) {
      // Sort by date descending
      entries.sort((a, b) => (b.gameDate || "").localeCompare(a.gameDate || ""));

      const slice = entries.slice(0, lastN);
      const played = slice.filter((e) => e.stats[stat] != null);

      if (played.length < minGames) continue;

      const avg =
        played.reduce((sum, e) => sum + e.stats[stat], 0) / played.length;

      const roster = rosterIndex.get(playerId) || null;

      if (teamFilter && (!roster || roster.team !== teamFilter)) continue;
      if (
        posFilter &&
        (!roster ||
          !roster.pos ||
          !roster.pos.toUpperCase().includes(posFilter))
      )
        continue;

      trending.push({
        playerId,
        name: entries[0].name,
        team: roster ? roster.team : entries[0].team,
        pos: roster ? roster.pos : null,
        lastNGames: played.length,
        stat: stat,
        avg,
        recent: slice.map((e) => ({
          gameDate: e.gameDate,
          value: e.stats[stat],
          team: e.team,
          raw: e.raw,
        })),
      });
    }

    trending.sort((a, b) => b.avg - a.avg);

    const limited = trending.slice(0, limit);

    const meta = {
      totalPlayers: byPlayer.size,
      trendingPlayers: limited.length,
      stat,
      lastN,
      minGames,
      limit,
      filters: {
        team: teamFilter || "",
        position: posFilter || "",
      },
      source: ["player_stats.json", "rosters.json"],
    };

    return jsonResponse(
      {
        data: limited,
        meta,
      },
      {
        status: 200,
        headers: { "cache-control": "public, max-age=30" },
      }
    );
  } catch (err) {
    console.error("api/trending error:", err);

    return jsonResponse(
      { error: "Failed to compute trending players." },
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

function clampInt(v, min, max) {
  const n = parseInt(v, 10);
  if (Number.isNaN(n)) return min;
  return Math.min(max, Math.max(min, n));
}

function extractRowsFromStatsPayload(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw.data)) return raw.data;
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

function numberOrNull(v) {
  if (v === undefined || v === null || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
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

  return {
    playerId: playerId != null ? String(playerId) : null,
    name,
    team: teamAbbr ? String(teamAbbr).toUpperCase() : "",
    gameDate,
    raw,
    stats: {
      pts: numberOrNull(raw.pts ?? raw.points),
      reb: numberOrNull(raw.reb ?? raw.rebounds),
      ast: numberOrNull(raw.ast ?? raw.assists),
      stl: numberOrNull(raw.stl ?? raw.steals),
      blk: numberOrNull(raw.blk ?? raw.blocks),
      fg3m: numberOrNull(raw.fg3m ?? raw.threes_made),
    },
  };
}

async function loadRosters(baseUrl) {
  try {
    const rosterUrl = new URL("/rosters.json", baseUrl);
    const res = await fetch(rosterUrl.toString(), {
      cf: { cacheTtl: 120, cacheEverything: true },
    });
    if (!res.ok) return [];
    const raw = await res.json();
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function buildRosterIndex(rosters) {
  const idx = new Map();
  rosters.forEach((p) => {
    const id =
      p.id != null ? String(p.id) : p.player_id != null ? String(p.player_id) : null;
    if (!id) return;
    const team =
      p.team ||
      p.team_abbr ||
      (p.team && p.team.abbreviation) ||
      "";
    const pos = p.pos || p.position || "";
    idx.set(id, {
      team: team ? String(team).toUpperCase() : "",
      pos,
    });
  });
  return idx;
}

function groupByPlayer(rows) {
  const map = new Map();
  rows.forEach((r) => {
    if (!r.playerId) return;
    if (!map.has(r.playerId)) map.set(r.playerId, []);
    map.get(r.playerId).push(r);
  });
  return map;
}
