async function loadGames() {
  const today = new Date().toISOString().split("T")[0];
  const res = await fetch(`/api/games/date/${today}`);
  const games = await res.json();

  const container = document.getElementById("games-container");
  container.innerHTML = "";

  if (!games.length) {
    container.innerHTML = `<div style="color:#94a3b8;">No games found.</div>`;
    return;
  }

  games.forEach(game => {
    const card = document.createElement("div");
    card.classList.add("game-card");

    // Determine badge style
    let badgeClass = "status-upcoming";
    if (game.status === "Final") badgeClass = "status-final";
    if (game.status?.toLowerCase().includes("live")) badgeClass = "status-live";

    // Main header
    card.innerHTML = `
      <div class="game-header">
        <div class="game-teams">
          ${game.away_team_abbr} @ ${game.home_team_abbr}
        </div>
        <div class="status-badge ${badgeClass}">
          ${game.status || "Scheduled"}
        </div>
      </div>

      <div class="game-info">
        ${game.time_et || "TBD"}
      </div>

      <div class="expand-btn">View More</div>

      <div class="expand-panel">
        <div class="injury-section">
          <div class="section-title">Injuries</div>
          <div class="injury-content">Loading...</div>
        </div>

        <div class="props-section">
          <div class="section-title">Prop Insights</div>
          <div class="props-content">Coming Soon...</div>
        </div>
      </div>
    `;

    // Expand logic
    const expandBtn = card.querySelector(".expand-btn");
    const panel = card.querySelector(".expand-panel");

    expandBtn.addEventListener("click", () => {
      panel.style.display = panel.style.display === "none" || panel.style.display === ""
        ? "block"
        : "none";
    });

    container.appendChild(card);
  });
}

document.addEventListener("DOMContentLoaded", loadGames);
