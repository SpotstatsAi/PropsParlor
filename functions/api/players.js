// functions/api/players.js 
export async function onRequest(context) {
  const { request } = context;

  if (request.method !== "GET") {
    return new Response(
      JSON.stringify({ error: "Method not allowed" }),
      {
        status: 405,
        headers: {
          "content-type": "application/json; charset=utf-8",
        },
      }
    );
  }

  try {
    const url = new URL(request.url);

    // rosters.json lives at repo root, served as a static file by Pages
    const rosterUrl = new URL("/rosters.json", url);

    const rosterRes = await fetch(rosterUrl.toString());
    if (!rosterRes.ok) {
      throw new Error(`Failed to load rosters.json (HTTP ${rosterRes.status})`);
    }

    const raw = await rosterRes.json();
    const players = Array.isArray(raw) ? raw : [];

    const meta = buildMeta(players);

    const body = JSON.stringify(
      {
        data: players,
        meta,
      },
      null,
      2
    );

    return new Response(body, {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
        // Cloudflare can edge-cache this for a minute
        "cache-control": "public, max-age=60",
      },
    });
  } catch (err) {
    console.error("api/players error:", err);

    return new Response(
      JSON.stringify({
        error: "Failed to load players.",
      }),
      {
        status: 500,
        headers: {
          "content-type": "application/json; charset=utf-8",
        },
      }
    );
  }
}

function buildMeta(players) {
  const totalPlayers = players.length;

  const teams = new Set();
  let guards = 0;
  let forwards = 0;
  let centers = 0;

  for (const p of players) {
    if (p.team) teams.add(p.team);

    const pos = (p.pos || p.position || "").toUpperCase();
    if (!pos) continue;

    if (pos.includes("G")) guards += 1;
    if (pos.includes("F")) forwards += 1;
    if (pos.includes("C")) centers += 1;
  }

  return {
    totalPlayers,
    uniqueTeams: teams.size,
    guards,
    forwards,
    centers,
    source: "rosters.json",
  };
}
