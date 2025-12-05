// functions/api/edges.js
//
// Edge candidates endpoint: compares a player's recent form vs their
// season-long average for a stat and returns players with the largest
// positive delta.
//
// Usage examples:
//   /api/edges
//   /api/edges?stat=pts&last_n=5&min_games=5&limit=50
//   /api/edges?team=LAL
//   /api/edges?position=G
//
// Edge score = lastNAvg(stat) - seasonAvg(stat)

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
      ? clampInt(sp.get("min_games"), lastN + 1, 82)
      : Math.max(8, lastN + 1);
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
    const rowsRaw = Array.isArray(statsRaw) ? statsRaw : statsRaw.data || [];
    const rows = rowsRaw.map(normalizeRow).filter((r) => !!r);

    // Load rosters for team/pos filters
    const rosters = await loadRosters(url);
    const rosterIndex = buildRosterIndex(rosters);

    const byPlayer = groupByPlayer(rows);

    const edges = [];

    for (const [playerId, entries] of byPlayer.entries()) {
      // sort by date descending
      entries.sort((a, b) => (b.gameDate || "").localeCompare(a.gameDate || ""));

      const statValues = entries
        .map((e) => e.stats[stat])
        .filter((v) => v != null);

      if (statValues.length < minGames) continue;

      const lastSlice = statValues.slice(0, lastN);
      const lastNAvg = lastSlice.reduce((s, v) => s + v, 0) / lastSlice.length;

      const seasonAvg =
        statValues.reduce((s, v) => s + v, 0) / statValues.length;

      const delta = lastNAvg - seasonAvg;
      if (!(delta > 0)) continue; // keep only positive edges

      const roster = rosterIndex.get(playerId) || null;
      if (teamFilter && (!roster || roster.team !== teamFilter)) continue;
      if (
        posFilter &&
        (!roster ||
          !roster.pos ||
          !roster.pos.toUpperCase().includes(posFilter))
      )
        continue;

      edges.push({
        playerId,
        name: entries[0].name,
        team: roster ? roster.team : entries[0].team,
        pos: roster ? roster.pos : null,
        stat,
        lastN,
        lastNGames: lastSlice.length,
        lastNAvg,
        seasonGames: statValues.length,
        seasonAvg,
        delta,
      });
    }

    edges.sort((a, b) => b.delta - a.delta);

    const limited = edges.slice(0, limit);

    const meta = {
      totalPlayers: byPlayer.size,
      edgePlayers: limited.length,
      stat,
      lastN,
      minGames,
      limit,
      filters: {
        team: teamFilter || "",
        position: posFilter || "",
      },
      source: "player_stats.json",
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
    console.error("api/edges error:", err);

    return jsonResponse({ error: "Failed to compute edge players." }, { status: 500 });
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
