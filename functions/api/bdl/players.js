// functions/api/bdl/players.js
//
// Live proxy to BallDontLie NBA players endpoint.
// Does NOT expose your API key to the client.
//
// Usage examples (from browser or frontend):
//   /api/bdl/players?search=lebron
//   /api/bdl/players?team_ids[]=14&per_page=50
//   /api/bdl/players?cursor=123
//
// This forwards query params directly to BDL:
//   https://api.balldontlie.io/v1/players?...  (with Authorization header)

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
    // Misconfiguration on Cloudflare side
    return jsonResponse(
      { error: "BDL_API_KEY is not configured in Cloudflare Pages env" },
      { status: 500 }
    );
  }

  try {
    const incomingUrl = new URL(request.url);

    // Base NBA API; change here if they ever move it.
    const bdlBase = "https://api.balldontlie.io/v1";
    const bdlUrl = new URL("/players", bdlBase);

    // Forward ALL query params directly to BDL
    incomingUrl.searchParams.forEach((value, key) => {
      bdlUrl.searchParams.append(key, value);
    });

    const headers = new Headers();
    headers.set("Authorization", apiKey);

    const bdlResponse = await fetch(bdlUrl.toString(), {
      method: "GET",
      headers,
      // keep it live-ish, but still allow small caching
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

    // Pass through BDL JSON as-is, plus a small meta wrapper
    return jsonResponse(
      {
        source: "balldontlie",
        endpoint: "/v1/players",
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
    console.error("api/bdl/players error:", err);

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
