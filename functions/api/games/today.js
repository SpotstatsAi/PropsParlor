export async function onRequest(context) {
  try {
    const today = new Date().toISOString().split("T")[0];

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
    const gamesToday = schedule.filter((g) => g.game_date === today);

    return new Response(JSON.stringify(gamesToday), {
      headers: { "Content-Type": "application/json" }
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err.message || "Unknown error" }),
      { status: 500 }
    );
  }
}
