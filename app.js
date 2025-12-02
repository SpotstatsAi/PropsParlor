async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url} (${res.status})`);
  }
  return res.json();
}

function renderGamesToday(games) {
  const container = document.getElementById("games-today");
  container.innerHTML = "";

  if (!games.length) {
    container.innerHTML = `<div class="pp-empty">No games scheduled for today.</div>`;
    return;
  }

  games.forEach((g) => {
    const card = document.createElement("div");
    card.className = "pp-card pp-card-clickable";

    const tipTime = g.time || "TBA";
    const status = g.status || "Scheduled";

    card.innerHTML = `
      <div class="pp-game-row">
        <div class="pp-game-main">
          <div class="pp-game-teams">
            ${g.visitor_team_abbr} @ ${g.home_team_abbr}
          </div>
          <div class="pp-game-extra">
            ${g.visitor_team_name} @ ${g.home_team_name}
          </div>
        </div>
        <div class="pp-game-side">
          <div class="pp-tag">${status}</div>
          <div class="pp-game-extra" style="text-align:right;margin-top:4px;">
            Tip: ${tipTime}
          </div>
        </div>
      </div>
    `;

    card.addEventListener("click", () => {
      renderGameDetails(g);
    });

    container.appendChild(card);
  });
}

function renderGameDetails(game) {
  const panel = document.getElementById("game-details");
  panel.innerHTML = `
    <h3 style="margin-top:0;margin-bottom:0.5rem;">
      ${game.visitor_team_name} @ ${game.home_team_name}
    </h3>
    <p class="pp-game-extra" style="margin-top:0;">
      Game ID: ${game.game_id} · ${game.game_date} · ${game.time || "TBA"} · Status: ${
    game.status || "Scheduled"
  }
    </p>

    <p class="pp-empty">
      This is where prop context will go: pace, usage, injuries, travel fatigue, plus
      green / yellow / red recommendations once we wire those endpoints.
    </p>
  `;
}

async function init() {
  const gamesTodayUrl = "/api/games/today";

  const container = document.getElementById("games-today");
  container.innerHTML = `<div class="pp-empty">Loading games…</div>`;

  try {
    const games = await fetchJson(gamesTodayUrl);
    renderGamesToday(games);
  } catch (err) {
    container.innerHTML = `<div class="pp-empty">Error: ${err.message}</div>`;
  }
}

document.addEventListener("DOMContentLoaded", init);
