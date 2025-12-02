export async function onRequest(context) {
  try {
    const { params } = context;
    const date = params.date; // YYYY-MM-DD

    if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return new Response(
        JSON.stringify({ error: "Invalid date. Use YYYY-MM-DD." }),
        { status: 400 },
      );
    }

    // The normalized JSON on GitHub Pages
    const scheduleUrl = "https://spotstatsai.github.io/SpotstatsAi/schedule.json";

    const scheduleRes = await fetch(scheduleUrl, {
      cf: { cacheEverything: true, cacheTtl: 120 },
    });

    if (!scheduleRes.ok) {
      return new Response(
        JSON.stringify({ error: "Failed to load schedule.json" }),
        { status: 500 },
      );
    }

    const schedule = await scheduleRes.json();

    // NEW FORMAT: schedule is a FLAT ARRAY
    const gamesForDate = schedule.filter(g => g.game_date === date);

    return new Response(JSON.stringify(gamesForDate), {
      headers: { "Content-Type": "application/json" },
    });

  } catch (err) {
    return new Response(
      JSON.stringify({ error: err.message || "Internal server error" }),
      { status: 500 },
    );
  }
}
