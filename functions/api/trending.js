// functions/api/trending.js
//
// Trending players from player_stats.json (aggregate per-player file).
//
// Uses the "last5_" fields where available.
// For stat=pts, score = last5_pts (fallback pts).
// For stat=reb,  score = last5_reb (fallback reb).
// For stat=ast,  score = last5_ast (fallback ast).
// For stat=usage, score = usage.
//
// Usage examples:
//   /api/trending
//   /api/trending?stat=pts&limit=30
//   /api/trending?team=LAL
//   /api/trending?position=G   <-- position requires rosters.json

export async function onRequest(context) {
  const { request } = context;

  if (request.method !== "GET") {
    return jsonResponse({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    const url = new URL(request.url);
    const sp = url.searchParams;

    const stat = (sp.get("stat") || "pts").toLowerCase(); // pts | reb | ast | usage
    const limit = sp.get("limit")
      ? clampInt(sp.get("limit"), 1, 200)
      : 50;

    const teamFilter = (sp.get("team") || "").trim().toUpperCase();
    const posFilter = (sp.get("position") || "").trim().toUpperCase();

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
    const players = normalizePlayersFromMap(statsRaw);

    // Load rosters for team/pos filters
    const rosters = await loadRosters(url);
    const rosterIndex = buildRosterIndex(rosters);

    const trending = [];

    for (const p of players) {
      const roster = rosterIndex.get(p.id) || rosterIndex.get(p.name) || null;
      const team = roster ? roster.team : p.team;
      const pos = roster ? roster.pos : null;

      if (teamFilter && team !== teamFilter) continue;
      if (
        posFilter &&
        (!pos || !pos.toUpperCase().includes(posFilter))
      )
        continue;

      const score = computeTrendingScore(p, stat);
      if (score == null) continue;

      trending.push({
        playerId: p.id,
        name: p.name,
        team,
        pos,
        stat,
        score,
        games: p.games,
        season: p.season,
        pts: p.pts,
        reb: p.reb,
        ast: p.ast,
        last5_pts: p.last5_pts,
        last5_reb: p.last5_reb,
        last5_ast: p.last5_ast,
        usage: p.usage,
      });
    }

    trending.sort((a, b) => b.score - a.score);

    const limited = trending.slice(0, limit);

    const meta = {
      totalPlayers: players.length,
      trendingPlayers: limited.length,
      stat,
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

function numberOrNull(v) {
  if (v === undefined || v === null || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

function normalizePlayersFromMap(raw) {
  if (!raw || typeof raw !== "object") return [];

  const players = [];
  for (const [name, v] of Object.entries(raw)) {
    if (!v || typeof v !== "object") continue;
    const id =
      v.player_id != null ? String(v.player_id) : name;
    const team = v.team ? String(v.team).toUpperCase() : "";
    players.push({
      id,
      name,
      team,
      season: v.season != null ? Number(v.season) : null,
      games: numberOrNull(v.games),
      pts: numberOrNull(v.pts),
      reb: numberOrNull(v.reb),
      ast: numberOrNull(v.ast),
      last5_pts: numberOrNull(v.last5_pts),
      last5_reb: numberOrNull(v.last5_reb),
      last5_ast: numberOrNull(v.last5_ast),
      usage: numberOrNull(v.usage),
      raw: v,
    });
  }
  return players;
}

function computeTrendingScore(p, stat) {
  switch (stat) {
    case "reb":
      return p.last5_reb ?? p.reb;
    case "ast":
      return p.last5_ast ?? p.ast;
    case "usage":
      return p.usage;
    case "pts":
    default:
      return p.last5_pts ?? p.pts;
  }
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
      p.id != null ? String(p.id) :
      p.player_id != null ? String(p.player_id) :
      null;
    const name = p.name || `${p.first_name || ""} ${p.last_name || ""}`.trim();
    const team =
      p.team ||
      p.team_abbr ||
      (p.team && p.team.abbreviation) ||
      "";
    const pos = p.pos || p.position || "";
    if (id) {
      idx.set(id, {
        team: team ? String(team).toUpperCase() : "",
        pos,
      });
    }
    if (name) {
      idx.set(name, {
        team: team ? String(team).toUpperCase() : "",
        pos,
      });
    }
  });
  return idx;
}
