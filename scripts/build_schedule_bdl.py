import os
import json
import time
import requests
from datetime import datetime, timedelta

BDL_API_KEY = os.environ.get("BDL_API_KEY")
if not BDL_API_KEY:
    raise RuntimeError("Missing BDL_API_KEY GitHub Codespace/Actions secret")

HEADERS = {"Authorization": BDL_API_KEY}
BASE_URL = "https://api.balldontlie.io/v1"


def fetch_all_paginated(endpoint, params=None, per_page=100):
    if params is None:
        params = {}

    page = 1
    all_data = []

    while True:
        p = dict(params)
        p["per_page"] = per_page
        p["page"] = page

        resp = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=p)
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


def build_schedule(days_back=3, days_forward=14):
    start_date = (datetime.utcnow() - timedelta(days=days_back)).date()
    end_date = (datetime.utcnow() + timedelta(days=days_forward)).date()

    games = fetch_all_paginated(
        "games",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    schedule = []

    for g in games:
        home = g.get("home_team") or {}
        away = g.get("visitor_team") or {}

        game_date = (g.get("date") or "")[:10]

        item = {
            "game_id": g.get("id"),
            "game_date": game_date,
            "time_et": g.get("time") or "TBD",
            "status": g.get("status"),
            "season": g.get("season"),
            "period": g.get("period"),

            "home_team_id": home.get("id"),
            "home_team_name": home.get("full_name"),
            "home_team_abbr": home.get("abbreviation"),

            "away_team_id": away.get("id"),
            "away_team_name": away.get("full_name"),
            "away_team_abbr": away.get("abbreviation"),
        }

        schedule.append(item)

    with open("schedule.json", "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)


if __name__ == "__main__":
    build_schedule()
