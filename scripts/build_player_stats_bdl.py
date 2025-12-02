import os
import json
import time
import requests
from datetime import datetime, timedelta

BDL_API_KEY = os.environ.get("BDL_API_KEY")
if not BDL_API_KEY:
    raise RuntimeError("BDL_API_KEY env var (GitHub secret) is required")

HEADERS = {"Authorization": BDL_API_KEY}
BASE_URL = "https://api.balldontlie.io/v1"


def fetch_all_paginated(endpoint, params=None, per_page=100):
    """
    Generic helper to fetch all pages from a BDL v2 endpoint.
    """
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
        # be gentle with rate limits
        time.sleep(0.25)

    return all_data


def build_rosters_and_player_base():
    """
    Build:
      - rosters.json: flat list of players with team info
      - player_stats_base.json: minimal player info (id, name, team, position)
    """
    players = fetch_all_paginated("players")

    rosters = []
    base_stats = []

    for p in players:
        team = p.get("team") or {}

        item = {
            "player_id": p.get("id"),
            "first_name": p.get("first_name"),
            "last_name": p.get("last_name"),
            "full_name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "position": p.get("position"),
            "height": p.get("height"),
            "weight": p.get("weight"),
            "team_id": team.get("id"),
            "team_name": team.get("full_name"),
            "team_abbr": team.get("abbreviation")
        }
        rosters.append(item)

        base_stats.append({
            "player_id": item["player_id"],
            "full_name": item["full_name"],
            "team_abbr": item["team_abbr"],
            "position": item["position"]
        })

    with open("rosters.json", "w", encoding="utf-8") as f:
        json.dump(rosters, f, indent=2)

    with open("player_stats_base.json", "w", encoding="utf-8") as f:
        json.dump(base_stats, f, indent=2)


def build_player_stats_from_season(current_season: int):
    """
    Build player_stats.json with season averages.
    Uses BDL /season_averages endpoint keyed by player_id.
    """
    with open("player_stats_base.json", "r", encoding="utf-8") as f:
        base_stats = json.load(f)

    player_ids = [p["player_id"] for p in base_stats if p["player_id"]]

    all_stats = []
    chunk_size = 100

    for i in range(0, len(player_ids), chunk_size):
        chunk = player_ids[i:i + chunk_size]
        params = {
            "season": current_season
        }
        # BDL v2 season_averages accepts multiple player_ids[]
        for pid in chunk:
            params.setdefault("player_ids[]", []).append(pid)

        resp = requests.get(f"{BASE_URL}/season_averages", headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        for row in data:
            pid = row.get("player_id")
            base = next((b for b in base_stats if b["player_id"] == pid), None)
            if not base:
                continue

            merged = {
                "player_id": pid,
                "full_name": base["full_name"],
                "team_abbr": base["team_abbr"],
                "position": base["position"],
                "games_played": row.get("games_played"),
                "min": row.get("min"),
                "pts": row.get("pts"),
                "reb": row.get("reb"),
                "ast": row.get("ast"),
                "stl": row.get("stl"),
                "blk": row.get("blk"),
                "turnover": row.get("turnover"),
                "fg3a": row.get("fg3a"),
                "fg3m": row.get("fg3m"),
                "fg3_pct": row.get("fg3_pct"),
                "fg_pct": row.get("fg_pct"),
                "fta": row.get("fta"),
                "ft_pct": row.get("ft_pct")
            }
            all_stats.append(merged)

        time.sleep(0.25)

    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2)


def build_schedule(days_back: int = 2, days_forward: int = 14):
    """
    Build schedule.json from BDL /games data.
    """
    start_date = (datetime.utcnow() - timedelta(days=days_back)).date()
    end_date = (datetime.utcnow() + timedelta(days=days_forward)).date()

    games = fetch_all_paginated(
        "games",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    )

    schedule = []
    for g in games:
        home = g.get("home_team") or {}
        visitor = g.get("visitor_team") or {}

        item = {
            "game_id": g.get("id"),
            "game_date": g.get("date", "")[:10],  # YYYY-MM-DD
            "status": g.get("status"),
            "season": g.get("season"),
            "period": g.get("period"),
            "time": g.get("time"),  # may be None
            "home_team_id": home.get("id"),
            "home_team_name": home.get("full_name"),
            "home_team_abbr": home.get("abbreviation"),
            "visitor_team_id": visitor.get("id"),
            "visitor_team_name": visitor.get("full_name"),
            "visitor_team_abbr": visitor.get("abbreviation")
        }
        schedule.append(item)

    with open("schedule.json", "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)


def main():
    current_season = datetime.utcnow().year  # adjust if you want a fixed season

    print("Building rosters + player_stats_base...")
    build_rosters_and_player_base()

    print("Building player_stats.json...")
    build_player_stats_from_season(current_season)

    print("Building schedule.json...")
    build_schedule()

    print("All BDL data built successfully.")


if __name__ == "__main__":
    main()
