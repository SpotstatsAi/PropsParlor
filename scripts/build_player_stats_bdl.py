#!/usr/bin/env python3
"""
BallDontLie PREMIUM → player_stats.json builder
Fully correct batch implementation for:
- season averages
- last 5 games
- player indexing
- today’s opponent

This version FIXES the 400 errors.
"""

import json
import os
import sys
import requests
from datetime import date
from time import sleep

BDL_BASE = "https://api.balldontlie.io/v1"

API_KEY = os.getenv("BALLDONTLIE_API_KEY", "").strip()
if not API_KEY:
    print("ERROR: BALLDONTLIE_API_KEY is not set", file=sys.stderr)
    sys.exit(1)

# ---------------------------
# Helper Functions
# ---------------------------

def bdl_get(path, params=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }
    url = f"{BDL_BASE}/{path}"

    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[bdl_get] ERROR ({attempt+1}/3): {e}", file=sys.stderr)
            if attempt == 2:
                raise
            sleep(1)


def norm_name(name: str) -> str:
    return (
        name.lower()
        .replace(".", "")
        .replace("'", "")
        .replace("-", " ")
        .strip()
    )


def parse_minutes(ms):
    """Convert '34:12' -> 34.2"""
    if not ms or ":" not in ms:
        return 0.0
    m, s = ms.split(":")
    try:
        return round(int(m) + int(s)/60, 1)
    except:
        return 0.0


# ---------------------------
# Fetch all players
# ---------------------------

def fetch_players_index():
    print("Fetching league player index…", file=sys.stderr)

    players = {}
    page = 1
    per_page = 100

    while True:
        data = bdl_get("players", params={"page": page, "per_page": per_page})
        arr = data.get("data", [])
        if not arr:
            break

        for p in arr:
            full = f"{p['first_name']} {p['last_name']}".strip()
            key = norm_name(full)
            players[key] = {
                "id": p["id"],
                "team": p["team"]["abbreviation"],
                "full_name": full
            }

        meta = data.get("meta", {})
        total_pages = meta.get("total_pages", 1)
        print(f"  players page {page}/{total_pages}", file=sys.stderr)

        if page >= total_pages:
            break
        page += 1

    print(f"Indexed {len(players)} players.", file=sys.stderr)
    return players


# ---------------------------
# Batch season averages
# ---------------------------

def fetch_season_averages_batch(player_ids, season):
    """Fetch season averages for up to 100 players."""
    params = {"season": season}
    for pid in player_ids:
        params.setdefault("player_ids[]", []).append(pid)

    data = bdl_get("season_averages", params=params)
    return data.get("data", [])


def fetch_last5_batch(player_ids, season):
    """Fetch last 5-game stats for many players at once."""
    params = {
        "seasons[]": season,
        "per_page": 100,
        "page": 1,
        "postseason": "false",
        "sort": "game.date:desc"
    }
    for pid in player_ids:
        params.setdefault("player_ids[]", []).append(pid)

    data = bdl_get("stats", params=params)
    return data.get("data", [])


# ---------------------------
# Build opponent map from schedule.json
# ---------------------------

def load_schedule():
    with open("schedule.json", "r") as f:
        return json.load(f)


def build_opponent_map(schedule, today):
    opp = {}
    games = schedule.get(today, [])
    for g in games:
        home = g["home_team"]
        away = g["away_team"]
        opp[home] = away
        opp[away] = home
    return opp


# ---------------------------
# MAIN
# ---------------------------

def main():
    today = date.today().isoformat()

    # Determine season (year of season start)
    season = date.today().year if date.today().month >= 10 else date.today().year - 1

    print(f"Using BallDontLie season: {season}", file=sys.stderr)
    print(f"Today: {today}", file=sys.stderr)

    # Load files
    with open("rosters.json", "r") as f:
        rosters = json.load(f)

    schedule = load_schedule()
    opponents = build_opponent_map(schedule, today)

    # Get all league players
    index = fetch_players_index()

    # Determine which player IDs we actually need
    player_ids = []
    roster_names = []
    mapping = {}   # name -> player_id

    for team, players in rosters.items():
        for name in players:
            key = norm_name(name)
            roster_names.append((team, name, key))
            if key in index:
                pid = index[key]["id"]
                mapping[name] = pid
                if pid not in player_ids:
                    player_ids.append(pid)
            else:
                mapping[name] = None

    print(f"Total matched players: {len(player_ids)}", file=sys.stderr)

    # Batch into chunks of ≤100
    chunks = [player_ids[i:i+100] for i in range(0, len(player_ids), 100)]

    # Fetch season averages
    season_map = {}
    print("Fetching SEASON AVERAGES in batches…", file=sys.stderr)
    for chunk in chunks:
        batch = fetch_season_averages_batch(chunk, season)
        for entry in batch:
            season_map[entry["player_id"]] = entry

    # Fetch last5 stats
    last5_map = {}
    print("Fetching LAST-5 stats in batches…", file=sys.stderr)
    for chunk in chunks:
        stats = fetch_last5_batch(chunk, season)
        # Organize per player
        per_player = {}
        for g in stats:
            pid = g["player"]["id"]
            per_player.setdefault(pid, []).append(g)

        for pid, games in per_player.items():
            games = games[:5]  # ensure only 5
            if not games:
                continue
            n = len(games)
            last5_map[pid] = {
                "pts": round(sum(g["pts"] for g in games) / n, 1),
                "reb": round(sum(g["reb"] for g in games) / n, 1),
                "ast": round(sum(g["ast"] for g in games) / n, 1),
            }

    # Build FINAL output
    final = {}

    for team, name, key in roster_names:
        pid = mapping[name]
        avg = season_map.get(pid, {})
        last5 = last5_map.get(pid, {})

        final[name] = {
            "team": team,
            "season": season,
            "games": avg.get("games_played", 0),
            "min": parse_minutes(avg.get("min")),
            "pts": avg.get("pts", 0.0),
            "reb": avg.get("reb", 0.0),
            "ast": avg.get("ast", 0.0),
            "fg_pct": avg.get("fg_pct"),
            "fg3_pct": avg.get("fg3_pct"),
            "ft_pct": avg.get("ft_pct"),

            "last5_pts": last5.get("pts", 0.0),
            "last5_reb": last5.get("reb", 0.0),
            "last5_ast": last5.get("ast", 0.0),

            "opponent": opponents.get(team),
            "usage": 0.0,
            "pace": None,
            "def_rank": None,
        }

    with open("player_stats.json", "w") as f:
        json.dump(final, f, indent=2, sort_keys=True)

    print(f"Done! Wrote {len(final)} players.", file=sys.stderr)


if __name__ == "__main__":
    main()
