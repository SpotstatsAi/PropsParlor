// functions/api/players.js

/**
 * Cloudflare Pages Function: /api/players
 *
 * Reads rosters.json (built by your GitHub Actions pipeline),
 * applies optional filters/sort from query params, and returns:
 * {
 *   data: [...players...],
 *   meta: { ...summary... }
 * }
 *
 * Supported query params:
 *  - search   (string)
 *  - team     (team abbreviation)
 *  - position (e.g. G, F, C, G-F, F-C)
 *  - sort     (name-asc | team | height-desc | weight-desc | jersey-asc)
 */

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

    const filters = {
      search: (searchParams.get("search") || "").trim(),
      team: (searchParams.get("team") || "").trim(),
      position: (searchParams.get("position") || "").trim(),
      sort: (searchParams.get("sort") || "name-asc").trim(),
    };

    // rosters.json lives at repo root and is served as a static asset
    const rosterUrl = new URL("/rosters.json", url);
    const rosterRes = await fetch(rosterUrl.toString(), {
      cf: { cacheTtl: 60, cacheEverything: true },
    });

    if (!rosterRes.ok) {
      throw new Error(`Failed to load rosters.json (HTTP ${rosterRes.status})`);
    }

    const raw = await rosterRes.json();
    const rawPlayers = Array.isArray(raw) ? raw : [];

    const players = rawPlayers.map(normalizePlayer);

    const filtered = filterPlayers(players, filters);
    const sorted = sortPlayers(filtered, filters.sort);
    const meta = buildMeta(players, sorted, filters);

    return jsonResponse(
      {
        data: sorted,
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
    console.error("api/players error:", err);

    return jsonResponse(
      { error: "Failed to load players." },
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

function parseHeightToInches(height) {
  if (!height || typeof height !== "string") return null;
  const match = height.match(/(\d+)-(\d+)/);
  if (!match) return null;
  const feet = parseInt(match[1], 10);
  const inches = parseInt(match[2], 10);
  if (Number.isNaN(feet) || Number.isNaN(inches)) return null;
  return feet * 12 + inches;
}

function normalizePlayer(raw) {
  const firstName = raw.first_name || raw.first || "";
  const lastName = raw.last_name || raw.last || "";
  const name = raw.name || `${firstName} ${lastName}`.trim();

  // support both flattened and BDL-style structures
  const teamAbbr =
    raw.team ||
    raw.team_abbr ||
    (raw.team && raw.team.abbreviation) ||
    "";

  const pos = raw.pos || raw.position || "";

  const heightStr =
    raw.height ||
    raw.height_str ||
    (raw.height_feet != null && raw.height_inches != null
      ? `${raw.height_feet}-${raw.height_inches}`
      : null);

  const weightStr =
    raw.weight ||
    raw.weight_pounds ||
    raw.weight_lbs ||
    null;

  const jersey =
    raw.jersey ||
    raw.jersey_number ||
    "";

  const heightInches = parseHeightToInches(heightStr);
  const weightNum = weightStr ? Number(weightStr) || null : null;

  return {
    id: raw.id,
    name,
    first_name: firstName,
    last_name: lastName,
    team: teamAbbr,
    pos,
    height: heightStr,
    weight: weightStr,
    jersey,
    heightInches,
    weightNum,
  };
}

function filterPlayers(players, filters) {
  const { search, team, position } = filters;
  let out = players.slice();

  if (search) {
    const q = search.toLowerCase();
    out = out.filter((p) => {
      return (
        (p.name && p.name.toLowerCase().includes(q)) ||
        (p.team && p.team.toLowerCase().includes(q)) ||
        (p.jersey && String(p.jersey).toLowerCase().includes(q))
      );
    });
  }

  if (team) {
    out = out.filter((p) => p.team === team);
  }

  if (position) {
    out = out.filter((p) => (p.pos || "") === position);
  }

  return out;
}

function sortPlayers(players, sortKeyRaw) {
  const sortKey = sortKeyRaw || "name-asc";
  const list = players.slice();

  switch (sortKey) {
    case "team":
      list.sort((a, b) => {
        if (a.team === b.team) {
          return (a.last_name || "").localeCompare(b.last_name || "");
        }
        return (a.team || "").localeCompare(b.team || "");
      });
      break;

    case "height-desc":
      list.sort((a, b) => {
        const ha = a.heightInches ?? -1;
        const hb = b.heightInches ?? -1;
        if (hb !== ha) return hb - ha;
        return (a.last_name || "").localeCompare(b.last_name || "");
      });
      break;

    case "weight-desc":
      list.sort((a, b) => {
        const wa = a.weightNum ?? -1;
        const wb = b.weightNum ?? -1;
        if (wb !== wa) return wb - wa;
        return (a.last_name || "").localeCompare(b.last_name || "");
      });
      break;

    case "jersey-asc":
      list.sort((a, b) => {
        const ja = parseInt(a.jersey, 10) || 0;
        const jb = parseInt(b.jersey, 10) || 0;
        if (ja !== jb) return ja - jb;
        return (a.last_name || "").localeCompare(b.last_name || "");
      });
      break;

    case "name-asc":
    default:
      list.sort((a, b) =>
        (a.last_name || a.name || "").localeCompare(
          b.last_name || b.name || ""
        )
      );
      break;
  }

  return list;
}

function buildMeta(allPlayers, filteredPlayers, filters) {
  const totalPlayers = allPlayers.length;
  const filteredCount = filteredPlayers.length;

  const teams = new Set();
  let guards = 0;
  let forwards = 0;
  let centers = 0;

  for (const p of allPlayers) {
    if (p.team) teams.add(p.team);

    const pos = (p.pos || "").toUpperCase();
    if (!pos) continue;

    if (pos.includes("G")) guards += 1;
    if (pos.includes("F")) forwards += 1;
    if (pos.includes("C")) centers += 1;
  }

  return {
    totalPlayers,
    filteredPlayers: filteredCount,
    uniqueTeams: teams.size,
    guards,
    forwards,
    centers,
    sort: filters.sort || "name-asc",
    filters: {
      search: filters.search || "",
      team: filters.team || "",
      position: filters.position || "",
    },
    source: "rosters.json",
  };
}
