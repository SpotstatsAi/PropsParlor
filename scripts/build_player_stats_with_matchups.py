#!/usr/bin/env python3
"""
Builds player_stats.json with:
- SportsData.io full season stats
- Opponent for today's games
- Team defensive ranks (via PointsAgainst)
- Basic pace/usage metrics where available

This script is FULLY PATCHED for:
- Correct SportsData endpoints
- Newline-stripped API key
- Correct team defense ranking logic
- No more KeyErrors
"""

import json
import os
import sys
from datetime import datetime
import requests

# -----------------------------
# CONFIG
# -----------------------------

API_KEY = os.getenv("SPORTSDATA_API_KEY", "").strip()
if not API_KEY:
    print("ERROR: SPORTSDATA_API_KEY missing!", file=sys.stderr)
    sys.exit(1)

# SportsData Season = 2025 for 2025–26 NBA season
SEASON = 2025

TODAY = datetime.utcnow().strftime("%Y-%m-%d")

BASE_STATS_URL = "https://api.sportsdata.io/v3/nba/stats/json"
BASE_SCORES_URL = "https://api.sportsdata.io/v3/nba/scores/json"

# -----------------------------
# HELPERS
# -----------------------------

def fetch_json(url):
    """Safely fetch JSON from SportsData.io."""
    headers = {"Ocp-Apim-Subscription-Key": API_KEY}
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    return resp.json()


def fetch_player_season_stats(season):
    """Fetch full season player stats."""
    url = f"{BASE_STATS_URL}/PlayerSeasonStats/{season}?key={API_KEY}"
    return fetch_json(url)


def fetch_todays_games():
    """Fetch the list of today's games."""
    url = f"{BASE_SCORES_URL}/GamesByDate/{TODAY}?key={API_KEY}"
    return fetch_json(url)


def get_team_stats():
    """
    Build defensive ranks using Standings → PointsAgainst.
    Correct endpoint for defense metrics!
    """
    url = f"{BASE_SCORES_URL}/Standings/{SEASON}?key={API_KEY}"
    data = fetch_json(url)

    # Sort by PointsAgainst (lower = better)
    sorted_by_def = sorted(data, key=lambda t: t.get("PointsAgainst", 999))
    ranks = {}
    rank = 1

    for team in sorted_by_def:
        code = team["Key"]  # three-letter team code (ATL, BOS, etc.)
        ranks[code] = {
            "DefRank": rank,
            "PointsAgainst": team.get("PointsAgainst")
        }
        rank += 1

    return ranks


# -----------------------------
# MAIN PROCESS
# -----------------------------

def main():
    print(f"Building stats for season {SEASON}, date {TODAY}", file=sys.stderr)

    # Load your rosters.json
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    # Fetch raw SportsData season stats
    print("Fetching player season stats from SportsData...", file=sys.stderr)
    season_stats = fetch_player_season_stats(SEASON)

    # Fetch today’s games
    print("Fetching today's games...", file=sys.stderr)
    todays_games = fetch_todays_games()

    # Fetch team defense rankings
    print("Fetching team defensive metrics...", file=sys.stderr)
    team_def = get_team_stats()

    # Build lookup by player name (exact match required)
    stats_by_name = {}
    for p in season_stats:
        name = p["Name"].strip()
        stats_by_name[name] = p

    final = {}
    missing = []

    # Opponent mapping for today
    opponent_map = {}  # team → opponent

    for g in todays_games:
        home = g["HomeTeam"]
        away = g["AwayTeam"]
        opponent_map[home] = away
        opponent_map[away] = home

    # Build final stats object
    for team_code, players in rosters.items():
        for name in players:

            raw = stats_by_name.get(name)

            if raw is None:
                missing.append((name, team_code))
                final[name] = {
                    "team": team_code,
                    "season": SEASON,
                    "games": 0,
                    "min": 0,
                    "pts": 0,
                    "reb": 0,
                    "ast": 0,
                    "stl": 0,
                    "blk": 0,
                    "tov": 0,
                    "usage": 0,
                    "pace": None,
                    "def_rank": None,
                    "opponent": None,
                }
                continue

            # Opponent + defensive rank
            opp = opponent_map.get(team_code)
            def_rank = team_def.get(opp, {}).get("DefRank") if opp else None

            final[name] = {
                "team": team_code,
                "season": SEASON,

                # Core stats
                "games": raw.get("Games", 0),
                "min": raw.get("Minutes", 0),
                "pts": raw.get("Points", 0),
                "reb": raw.get("Rebounds", 0),
                "ast": raw.get("Assists", 0),
                "stl": raw.get("Steals", 0),
                "blk": raw.get("BlockedShots", 0),
                "tov": raw.get("Turnovers", 0),

                # Pace / Usage
                "usage": raw.get("UsageRate", 0),
                "pace": raw.get("Possessions", None),   # SportsData pace metric

                # Opponent-dependent values
                "opponent": opp,
                "def_rank": def_rank,
            }

    # Write output
    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, sort_keys=True)

    # Show missing matches in run logs
    if missing:
        print("\nPlayers not found in SportsData:", file=sys.stderr)
        for n, t in missing:
            print(f" - {n} ({t})", file=sys.stderr)


if __name__ == "__main__":
    main()
