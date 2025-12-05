// Cloudflare Pages Function: /api/bdl/players
// Proxy to BallDontLie /players with normalization for the UI.
//
// Query params:
//   search    (required) - player name search string
//   per_page  (optional) - number of results, default 10, max 25

const BDL_BASE = "https://api.balldontlie.io/v1/"; // trailing slash required

export async function onRequest({ request, env }) {
  try {
    const url = new URL(request.url);
    const search = url.searchParams.get("search") || "";
    const perPageParam = url.searchParams.get("per_page") || "10";

    if (!search.trim()) {
      return jsonResponse(
        {
          data: [],
          meta: { error: "Missing search query" },
        },
        400
      );
    }

    let perPage = parseInt(perPageParam, 10);
    if (Number.isNaN(perPage) || perPage <= 0) perPage = 10;
    if (perPage > 25) perPage = 25;

    const apiKey = env.BDL_API_KEY;
    if (!apiKey) {
      return jsonResponse(
        {
          data: [],
          meta: { error: "BDL_API_KEY not configured in Cloudflare env" },
        },
        500
      );
    }

    // IMPORTANT: do NOT start the path with "/" – it would nuke "/v1".
    const bdlUrl = new URL("players", BDL_BASE);
    bdlUrl.searchParams.set("search", search);
    bdlUrl.searchParams.set("per_page", String(perPage));

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
    const raw = Array.isArray(bdlJson.data) ? bdlJson.data : [];

    const data = raw.map((p) => {
      const team = p.team || {};
      return {
        id: p.id,
        name: `${p.first_name || ""} ${p.last_name || ""}`.trim(),
        first_name: p.first_name || null,
        last_name: p.last_name || null,
        team: team.abbreviation || null,
        full_team: team.full_name || null,
        pos: p.position || null,
      };
    });

    return jsonResponse({
      data,
      meta: {
        total: bdlJson.meta?.total ?? null,
        per_page: bdlJson.meta?.per_page ?? null,
        search,
        source: "balldontlie",
      },
    });
  } catch (err) {
    return jsonResponse(
      {
        data: [],
        meta: {
          error: "Unexpected error in /api/bdl/players",
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
