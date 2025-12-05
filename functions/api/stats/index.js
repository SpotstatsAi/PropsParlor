// Cloudflare Pages Function: /api/stats
// Returns last N games for a player from BallDontLie, normalized for the UI.
//
// Query params:
//   player_id (required) - BDL player id
//   last_n   (optional)  - # of recent games to return (default 10, max 50)
//
// Example:
//   /api/stats?player_id=4&last_n=10

const BDL_BASE = "https://api.balldontlie.io/v1/"; // IMPORTANT: trailing slash

export async function onRequest({ request, env }) {
  try {
    const url = new URL(request.url);
    const playerId = url.searchParams.get("player_id");
    const lastNParam = url.searchParams.get("last_n") || "10";

    if (!playerId) {
      return jsonResponse(
        {
          data: [],
          meta: {
            error: "Missing player_id",
          },
        },
        400
      );
    }

    // Clamp last_n between 1 and 50
    let lastN = parseInt(lastNParam, 10);
    if (Number.isNaN(lastN) || lastN <= 0) lastN = 10;
    if (lastN > 50) lastN = 50;

    const apiKey = env.BDL_API_KEY;
    if (!apiKey) {
      return jsonResponse(
        {
          data: [],
          meta: {
            error: "BDL_API_KEY not configured in Cloudflare env",
          },
        },
        500
      );
    }

    // Build BallDontLie stats URL
    // NOTE: DO NOT START PATH WITH "/" OR IT WILL NUKE "/v1".
    const bdlUrl = new URL("stats", BDL_BASE);
    bdlUrl.searchParams.set("player_ids[]", String(playerId));
    bdlUrl.searchParams.set("per_page", String(lastN));
    bdlUrl.searchParams.set("postseason", "false");
    // (Optional) you can add seasons[] or date filters later.

    const bdlResp = await fetch(bdlUrl.toString(), {
      headers: {
        Authorization: `Bearer ${apiKey}`,
      },
    });

    if (!bdlResp.ok) {
      const upstreamText = await safeText(bdlResp);
      return jsonResponse(
        {
          data: [],
          meta: {
            error: "BallDontLie request failed",
            status: bdlResp.status,
            upstream: upstreamText ? { error: upstreamText } : undefined,
          },
        },
        502
      );
    }

    const bdlJson = await bdlResp.json();
    const rawRows = Array.isArray(bdlJson.data) ? bdlJson.data : [];

    // Normalize rows for the UI
    const rows = rawRows.map((row) => {
      const game = row.game || {};
      const team = row.team || {};
      const homeTeam = game.home_team || {};
      const visitorTeam = game.visitor_team || {};

      const isHome = homeTeam.id === team.id;
      const oppTeam = isHome ? visitorTeam : homeTeam;

      const gameDate = game.date ? String(game.date).slice(0, 10) : null;

      return {
        player_id: row.player?.id ?? row.player_id ?? null,
        game_id: game.id ?? null,

        game_date: gameDate,
        season: game.season ?? null,

        team: team.abbreviation || null,
        opponent: oppTeam.abbreviation || null,

        min: row.min ?? null,
        pts: row.pts ?? null,
        reb: row.reb ?? null,
        ast: row.ast ?? null,
        stl: row.stl ?? null,
        blk: row.blk ?? null,
        tov: row.turnover ?? row.turnovers ?? null,
        fgm: row.fgm ?? null,
        fga: row.fga ?? null,
        fg3m: row.fg3m ?? null,
        fg3a: row.fg3a ?? null,
        ftm: row.ftm ?? null,
        fta: row.fta ?? null,
      };
    });

    return jsonResponse({
      data: rows,
      meta: {
        playerId: playerId,
        lastN: rows.length,
        source: "balldontlie",
        upstream: {
          total: bdlJson.meta?.total ?? null,
          per_page: bdlJson.meta?.per_page ?? null,
        },
      },
    });
  } catch (err) {
    return jsonResponse(
      {
        data: [],
        meta: {
          error: "Unexpected error in /api/stats",
          detail: err instanceof Error ? err.message : String(err),
        },
      },
      500
    );
  }
}

function jsonResponse(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

async function safeText(resp) {
  try {
    return await resp.text();
  } catch {
    return null;
  }
}
