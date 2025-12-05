// functions/api/teams.js
//
// Groups players from rosters.json into teams.
//
// Usage examples:
//   /api/teams
//   /api/teams?team=LAL
//   /api/teams?search=james
//   /api/teams?position=G
//
// Tries to enrich team info from team_map.json if it exists at repo root.

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
      team: (searchParams.get("team") || "").trim().toUpperCase(),
      search: (searchParams.get("search") || "").trim(),
      position: (searchParams.get("position") || "").trim().toUpperCase(),
    };

    // Load rosters.json
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

    // Optional: load team_map.json for extra metadata
    const teamMap = await loadTeamMap(url);

    const { teams, allTeamsMeta } = groupPlayersByTeam(players, teamMap);

    const filteredTeams = filterTeams(teams, filters);
    const meta = buildMeta(allTeamsMeta, filteredTeams, filters);

    return jsonResponse(
      {
        data: filteredTeams,
        meta,
      },
      {
        status: 200,
        headers: {
          "cache-control": "public, max-age=60",
        },
      }
    );
  } catch (err) {
    console.error("api/teams error:", err);

    return jsonResponse(
      { error: "Failed to load teams." },
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
    team: teamAbbr ? String(teamAbbr).toUpperCase() : "",
    pos,
    height: heightStr,
    weight: weightStr,
    jersey,
    heightInches,
    weightNum,
  };
}

async function loadTeamMap(baseUrl) {
  try {
    const teamMapUrl = new URL("/team_map.json", baseUrl);
    const res = await fetch(teamMapUrl.toString(), {
      cf: { cacheTtl: 300, cacheEverything: true },
    });
    if (!res.ok) return null;

    const data = await res.json();
    return data || null;
  } catch {
    return null;
  }
}

function groupPlayersByTeam(players, teamMap) {
  const teams = new Map();

  players.forEach((p) => {
    const key = p.team || "FA"; // free agents / unknown
    if (!teams.has(key)) {
      const meta = resolveTeamMeta(key, teamMap);
      teams.set(key, {
        team: key,
        name: meta.name,
        city: meta.city,
        full_name: meta.full_name,
        conference: meta.conference,
        division: meta.division,
        colors: meta.colors,
        players: [],
        counts: {
          totalPlayers: 0,
          guards: 0,
          forwards: 0,
          centers: 0,
        },
      });
    }

    const bucket = teams.get(key);
    bucket.players.push(p);
    bucket.counts.totalPlayers += 1;

    const pos = (p.pos || "").toUpperCase();
    if (pos.includes("G")) bucket.counts.guards += 1;
    if (pos.includes("F")) bucket.counts.forwards += 1;
    if (pos.includes("C")) bucket.counts.centers += 1;
  });

  const teamList = Array.from(teams.values()).sort((a, b) =>
    a.team.localeCompare(b.team)
  );

  const allTeamsMeta = {
    totalTeams: teamList.length,
    totalPlayers: players.length,
  };

  return { teams: teamList, allTeamsMeta };
}

function resolveTeamMeta(teamAbbr, teamMap) {
  if (!teamMap) {
    return {
      name: teamAbbr,
      city: null,
      full_name: teamAbbr,
      conference: null,
      division: null,
      colors: null,
    };
  }

  // team_map.json could be an object keyed by abbr or an array
  let meta = null;

  if (Array.isArray(teamMap)) {
    meta =
      teamMap.find((t) => {
        const abbr =
          t.abbreviation || t.abbr || t.team || t.code || t.key || "";
        return String(abbr).toUpperCase() === teamAbbr;
      }) || null;
  } else if (typeof teamMap === "object" && teamMap !== null) {
    const direct =
      teamMap[teamAbbr] ||
      teamMap[teamAbbr.toUpperCase()] ||
      null;
    meta = direct;
  }

  if (!meta) {
    return {
      name: teamAbbr,
      city: null,
      full_name: teamAbbr,
      conference: null,
      division: null,
      colors: null,
    };
  }

  return {
    name: meta.name || meta.full_name || teamAbbr,
    city: meta.city || null,
    full_name: meta.full_name || meta.name || teamAbbr,
    conference: meta.conference || null,
    division: meta.division || null,
    colors: meta.colors || meta.color || null,
  };
}

function filterTeams(teams, filters) {
  const { team, search, position } = filters;

  return teams
    .filter((t) => {
      if (team && t.team !== team) return false;
      return true;
    })
    .map((t) => {
      let players = t.players;

      if (search) {
        const q = search.toLowerCase();
        players = players.filter((p) => {
          return (
            (p.name && p.name.toLowerCase().includes(q)) ||
            (p.jersey && String(p.jersey).toLowerCase().includes(q))
          );
        });
      }

      if (position) {
        players = players.filter((p) => {
          const pos = (p.pos || "").toUpperCase();
          return pos === position;
        });
      }

      return {
        ...t,
        players,
        counts: {
          totalPlayers: players.length,
          guards: players.filter((p) =>
            (p.pos || "").toUpperCase().includes("G")
          ).length,
          forwards: players.filter((p) =>
            (p.pos || "").toUpperCase().includes("F")
          ).length,
          centers: players.filter((p) =>
            (p.pos || "").toUpperCase().includes("C")
          ).length,
        },
      };
    })
    .filter((t) => t.counts.totalPlayers > 0);
}

function buildMeta(allTeamsMeta, filteredTeams, filters) {
  const filteredTeamsCount = filteredTeams.length;
  const filteredPlayersCount = filteredTeams.reduce(
    (sum, t) => sum + t.counts.totalPlayers,
    0
  );

  return {
    totalTeams: allTeamsMeta.totalTeams,
    totalPlayers: allTeamsMeta.totalPlayers,
    filteredTeams: filteredTeamsCount,
    filteredPlayers: filteredPlayersCount,
    filters: {
      team: filters.team || "",
      search: filters.search || "",
      position: filters.position || "",
    },
    source: ["rosters.json", "team_map.json"],
  };
}
