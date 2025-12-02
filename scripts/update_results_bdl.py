import os
import json
import time
import requests
from datetime import datetime, timedelta

BDL_API_KEY = os.environ.get("BDL_API_KEY")
if not BDL_API_KEY:
    raise RuntimeError("Missing BDL_API_KEY GitHub secret")

HEADERS = {"Authorization": BDL_API_KEY}
BDL_BASE_URL = "https://api.balldontlie.io/v1"


def fetch_all_paginated(endpoint, params=None, per_page=100):
    if params is None:
        params = {}

    page = 1
    all_data = []

    while True:
        p = dict(params)
        p["per_page"] = per_page
        p["page"] = page

        resp = requests.get(f"{BDL_BASE_URL}/{endpoint}", headers=HEADERS, params=p)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", [])
        all_data.extend(items)

        meta = data.get("meta", {})
        if not meta or page >= meta.get("total_pages", 1):
            break

        page += 1
        time.sleep(0.15)

    return all_data


def update_results(lookback_days: int = 5):
    """
    Load schedule_master.json, fetch BDL games for the last `lookback_days`,
    and merge results into the matching games. Then write schedule.json.
    """

    # Load master schedule (built from NBA.com)
    with open("schedule_master.json", "r", encoding="utf-8") as f:
        master = json.load(f)

    # Build a quick index by (date, home_abbr, away_abbr)
    index = {}
    for g in master:
        key = (
            g.get("game_date"),
            g.get("home_team_abbr"),
            g.get("away_team_abbr"),
        )
        if all(key):
            index[key] = g

    # BDL: fetch recent games only (yesterday, etc.)
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=lookback_days)
    end_date = today - timedelta(days=1)

    if end_date < start_date:
        # No past days to update yet
        with open("schedule.json", "w", encoding="utf-8") as f:
            json.dump(master, f, indent=2)
        return

    bdl_games = fetch_all_paginated(
        "games",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    for bg in bdl_games:
        bdl_id = bg.get("id")

        # BDL uses ISO timestamps; take YYYY-MM-DD
        game_date = (bg.get("date") or "")[:10]

        home = bg.get("home_team") or {}
        away = bg.get("visitor_team") or {}

        home_abbr = home.get("abbreviation")
        away_abbr = away.get("abbreviation")

        key = (game_date, home_abbr, away_abbr)

        game = index.get(key)
        if not game:
            # If for some reason the abbreviations don't match exactly,
            # we just skip; no crash.
            continue

        # Merge scores and status
        game["bdl_game_id"] = bdl_id
        game["status"] = bg.get("status") or game.get("status") or "Final"
        game["home_score"] = bg.get("home_team_score")
        game["away_score"] = bg.get("visitor_team_score")

        # Store full BDL payload if we want to use more detail later
        game["bdl_payload"] = bg

    # Write merged schedule
    with open("schedule.json", "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2)


if __name__ == "__main__":
    update_results()
