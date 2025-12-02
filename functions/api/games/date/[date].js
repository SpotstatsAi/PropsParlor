export async function onRequest(context) {
  try {
    const { params } = context;
    const date = params.date; // YYYY-MM-DD

    if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return new Response(
        JSON.stringify({ error: "Invalid date. Use YYYY-MM-DD." }),
        { status: 400 }
      );
    }

    const scheduleUrl = "https://spotstatsai.github.io/SpotstatsAi/schedule.json";

    const scheduleRes = await fetch(scheduleUrl, {
      cf: { cacheEverything: true, cacheTtl: 3600 }
    });

    if (!scheduleRes.ok) {
      return new Response(
        JSON.stringify({ error: "Failed to load schedule.json" }),
        { status: 500 }
      );
    }

    const schedule = await scheduleRes.json();
    const games = schedule.filter((g) => g.game_date === date);

    return new Response(JSON.stringify(games), {
      headers: { "Content-Type": "application/json" }
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err.message || "Unknown error" }),
      { status: 500 }
    );
  }
}
