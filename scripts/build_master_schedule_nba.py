import json
import requests
from datetime import datetime

NBA_SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"


def build_internal_game_id(game_date: str, index_for_day: int) -> str:
    """
    Our own stable internal ID, so we never depend on NBA.com or BDL IDs.

    Example: game_date = '2025-12-01', index_for_day = 1
    -> 'g_20251201_001'
    """
    compact = game_date.replace("-", "")
    return f"g_{compact}_{index_for_day:03d}"


def build_master_schedule():
    resp = requests.get(NBA_SCHEDULE_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # This structure is based on the current NBA scheduleLeagueV2 format.
    game_dates = (
        data.get("leagueSchedule", {})
        .get("gameDates", [])
    )

    master = []

    for gd in game_dates:
        # Expect something like '2025-12-01'
        game_date = gd.get("gameDate")
        if not game_date:
            # Some versions include 'gameDate' as 'YYYY-MM-DD', some as 'YYYY-MM-DDT00:00:00Z'
            raw_date = gd.get("gameDateEst") or gd.get("gameDateUTC")
            if raw_date:
                game_date = raw_date[:10]

        if not game_date:
            continue

        games = gd.get("games", [])
        index_for_day = 0

        for g in games:
            index_for_day += 1

            nba_game_id = g.get("gameId")

            home_team = g.get("homeTeam", {}) or {}
            away_team = g.get("awayTeam", {}) or {}

            home_abbr = home_team.get("teamTricode")
            away_abbr = away_team.get("teamTricode")

            # NBA usually provides this
            time_et = g.get("gameTimeET") or "TBD"

            # Game status (scheduled / in progress / final, etc.)
            status = "Scheduled"
