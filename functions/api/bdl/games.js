// functions/api/bdl/games.js
//
// Live proxy to BallDontLie NBA games endpoint.
// Usage:
//   /api/bdl/games
//   /api/bdl/games?dates[]=2025-12-05
//   /api/bdl/games?team_ids[]=14&seasons[]=2024

export async function onRequest(context) {
  const { request, env } = context;

  if (request.method !== "GET") {
    return jsonResponse(
      { error: "Method not allowed" },
      { status: 405 }
    );
  }

  const apiKey = env.BDL_API_KEY;
  if (!apiKey) {
    return jsonResponse(
      { error: "BDL_API_KEY is not configured in Cloudflare Pages env" },
      { status: 500 }
    );
  }

  try {
    const incomingUrl = new URL(request.url);

    // Correct base + path: /v1/games
    const bdlBase = "https://api.balldontlie.io";
    const bdlUrl = new URL("/v1/games", bdlBase);

    // Forward all query params
    incomingUrl.searchParams.forEach((value, key) => {
      bdlUrl.searchParams.append(key, value);
    });

    const headers = new Headers();
    headers.set("Authorization", apiKey);

    const bdlResponse = await fetch(bdlUrl.toString(), {
      method: "GET",
      headers,
      cf: {
        cacheTtl: 5,
        cacheEverything: false,
      },
    });

    const text = await bdlResponse.text();
    let json;
    try {
      json = JSON.parse(text);
    } catch {
      json = { raw: text };
    }

    if (!bdlResponse.ok) {
      return jsonResponse(
        {
          error: "BallDontLie request failed",
          status: bdlResponse.status,
          upstream: json,
        },
        { status: 502 }
      );
    }

    return jsonResponse(
      {
        source: "balldontlie",
        endpoint: "/v1/games",
        forwarded_query: Object.fromEntries(incomingUrl.searchParams.entries()),
        data: json,
      },
      {
        status: 200,
        headers: {
          "cache-control": "public, max-age=5",
        },
      }
    );
  } catch (err) {
    console.error("api/bdl/games error:", err);

    return jsonResponse(
      { error: "Unexpected error calling BallDontLie" },
      { status: 500 }
    );
  }
}

/* ------------ helpers ------------ */

function jsonResponse(body, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("content-type", "application/json; charset=utf-8");

  return new Response(JSON.stringify(body, null, 2), {
    ...options,
    headers,
  });
}
