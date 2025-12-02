export async function onRequest(context) {
  try {
    const url = new URL(context.request.url);
    const start = url.searchParams.get("start");
    const end = url.searchParams.get("end");

    if (
      !start ||
      !end ||
      !/^\d{4}-\d{2}-\d{2}$/.test(start) ||
      !/^\d{4}-\d{2}-\d{2}$/.test(end)
    ) {
      return new Response(
        JSON.stringify({ error: "start and end (YYYY-MM-DD) are required" }),
        { status: 400 },
      );
    }

    const scheduleUrl = "https://spotstatsai.github.io/SpotstatsAi/schedule.json";

    const scheduleRes = await fetch(scheduleUrl, {
      cf: { cacheEverything: true, cacheTtl: 3600 },
    });

    if (!scheduleRes.ok) {
      return new Response(
        JSON.stringify({ error: "Failed to load schedule.json" }),
        { status: 500 },
      );
    }

    const schedule = await scheduleRes.json();

    const startTime = new Date(start).getTime();
    const endTime = new Date(end).getTime();

    const games = schedule.filter((g) => {
      const t = new Date(g.game_date).getTime();
      return t >= startTime && t <= endTime;
    });

    return new Response(JSON.stringify(games), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err.message || "Unknown error" }),
      { status: 500 },
    );
  }
}
