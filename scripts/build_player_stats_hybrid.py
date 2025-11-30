#!/usr/bin/env python3
"""
Hybrid FREE-TIER SAFE player_stats.json builder

Uses ONLY:
- PlayerSeasonStats  (allowed)
- Standings          (allowed)
- schedule.json      (your own file)

Adds to each player:
- Per-game averages
- Opponent (from today's schedule.json)
- Opponent defense rank
- Team record
- Opponent record
- Usage
- Pace
- Streaks

NEVER hits forbidden SportsData.io endpoints.
No GamesByDate. No PlayerGameStats.
No 401/403 errors.
"""

import json
import os
import sys
from datetime import datetime
import requests

# --------------------------------------
# CONFIG
# --------------------------------------

API_KEY = os.getenv("SPORTSDATA_API_KEY", "").strip()
if not API_KEY:
    print("ERROR: SPORTSDATA_API_KEY is missing from GitHub Secrets!", file=sys.stderr)
    sys.exit(1)

SEASON = 2025  # SportsData season key for 2025–26
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

BASE_STATS_URL = "https://api.sportsdata.io/v3/nba/stats/json"
BASE_SCORES_URL = "https://api.sportsdata.io/v3/nba/scores/json"

# --------------------------------------
# HELPERS
# --------------------------------------

def fetch_json(url):
    """Fetch JSON with HEADER AUTH ONLY (key= NOT used)."""
    headers = {"Ocp-Apim-Subscription-Key": API_KEY}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_player_season_stats():
    """Season totals + advanced — allowed on free tier."""
    url = f"{BASE_STATS_URL}/PlayerSeasonStats/{SEASON}"
    return fetch_json(url)


def fetch_standings():
    """Contains record, PF, PA, streaks, ranks — allowed on free tier."""
    url = f"{BASE_SCORES_URL}/Standings/{SEASON}"
    return fetch_json(url)


def load_schedule():
    """Use LOCAL schedule.json to get today's matchups."""
    with open("schedule.json", "r", encoding="utf-8") as f:
        schedule = json.load(f)
    return schedule.get(TODAY, [])


# --------------------------------------
# MAIN LOGIC
# --------------------------------------

def main():
    print("Building FREE-TIER hybrid stats…", file=sys.stderr)

    # Load rosters
    with open("roosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    # Fetch allowable API data
    print("Fetching season stats…", file=sys.stderr)
    season_stats = fetch_player_season_stats()

    print("Fetching standings…", file=sys.stderr)
    standings = fetch_standings()

    print("Loading schedule.json…", file=sys.stderr)
    todays_games = load_schedule()

    # Build lookup: player name → season stats
    stats_by_name = {p["Name"].strip(): p for p in season_stats}

    # Build standings lookups
    team_info = {}
    for t in standings:
        code = t["Key"]
        wins = t.get("Wins", 0)
        losses = t.get("Losses", 0)

        team_info[code] = {
            "record": f"{wins}-{losses}",
            "win_pct": t.get("Percentage", 0),
            "streak": t.get("StreakDescription", ""),
            "points_for": t.get("PointsFor"),
            "points_against": t.get("PointsAgainst"),
            "conf_rank": t.get("ConferenceRank"),
            "div_rank": t.get("DivisionRank"),
        }

    # Defense rank = sorted by PointsAgainst
    sorted_by_def = sorted(standings, key=lambda t: t.get("PointsAgainst", 9999))
    defense_rank = {t["Key"]: i + 1 for i, t in enumerate(sorted_by_def)}

    # Build matchup map from schedule.json
    opponent_map = {}
    for g in todays_games:
        away = g["away_team"]
        home = g["home_team"]
        opponent_map[away] = home
        opponent_map[home] = away

    # ----------------------------------
    # BUILD FINAL OUTPUT
    # ----------------------------------

    final = {}
    missing = []

    for team_code, players in rosters.items():
        for name in players:
            raw = stats_by_name.get(name)

            if raw is None:
                missing.append((name, team_code))
                final[name] = {
                    "team": team_code,
                    "games": 0,
                    "pts": 0,
                    "reb": 0,
                    "ast": 0,
                    "stl": 0,
                    "blk": 0,
                    "tov": 0,
                    "usage": 0,
                    "pace": None,
                    "opponent": None,
                    "def_rank": None,
                    "team_record": None,
                    "opp_record": None,
                }
                continue

            # Per-game conversion
            games = raw.get("Games", 0)
            g = games if games > 0 else 1

            opp = opponent_map.get(team_code)

            team_rec = team_info.get(team_code, {})
            opp_rec = team_info.get(opp, {}) if opp else {}

            final[name] = {
                "team": team_code,
                "season": SEASON,

                # Per-game averages
                "games": games,
                "min": raw.get("Minutes", 0) / g,
                "pts": raw.get("Points", 0) / g,
                "reb": raw.get("Rebounds", 0) / g,
                "ast": raw.get("Assists", 0) / g,
                "stl": raw.get("Steals", 0) / g,
                "blk": raw.get("BlockedShots", 0) / g,
                "tov": raw.get("Turnovers", 0) / g,

                # Advanced stats
                "usage": raw.get("UsageRate", 0),
                "pace": raw.get("Possessions", None),

                # Matchup
                "opponent": opp,
                "def_rank": defense_rank.get(opp) if opp else None,

                # Team record
                "team_record": team_rec.get("record"),
                "team_win_pct": team_rec.get("win_pct"),
                "team_streak": team_rec.get("streak"),

                # Opponent record
                "opp_record": opp_rec.get("record"),
                "opp_win_pct": opp_rec.get("win_pct"),
                "opp_streak": opp_rec.get("streak"),
                "opp_points_for": opp_rec.get("points_for"),
                "opp_points_against": opp_rec.get("points_against"),
                "opp_conf_rank": opp_rec.get("conf_rank"),
                "opp_div_rank": opp_rec.get("div_rank"),
            }

    # Write JSON
    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, sort_keys=True)

    if missing:
        print("\nPlayers missing from API:", file=sys.stderr)
        for n, t in missing:
            print(f" - {n} ({t})")


if __name__ == "__main__":
    main()
