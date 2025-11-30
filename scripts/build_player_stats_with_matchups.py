#!/usr/bin/env python3
"""
Enhanced player_stats.json generator.

Includes:
- SportsData season stats
- Per-game averages (PTS/REB/AST/etc)
- Opponent for today's games
- Opponent defensive rank
- Usage + Pace
- Team record + opponent record
- Opponent streak, rank, points for/against
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

SEASON = 2025                     # 2025–26 season
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

BASE_STATS_URL = "https://api.sportsdata.io/v3/nba/stats/json"
BASE_SCORES_URL = "https://api.sportsdata.io/v3/nba/scores/json"


# -----------------------------
# FETCH HELPERS
# -----------------------------

def fetch_json(url):
    headers = {"Ocp-Apim-Subscription-Key": API_KEY}
    r = requests.get(url, headers=headers, timeout=25)
    r.raise_for_status()
    return r.json()

def fetch_player_season_stats():
    url = f"{BASE_STATS_URL}/PlayerSeasonStats/{SEASON}?key={API_KEY}"
    return fetch_json(url)

def fetch_todays_games():
    url = f"{BASE_SCORES_URL}/GamesByDate/{TODAY}?key={API_KEY}"
    return fetch_json(url)

def fetch_team_standings():
    url = f"{BASE_SCORES_URL}/Standings/{SEASON}?key={API_KEY}"
    return fetch_json(url)


# -----------------------------
# MAIN
# -----------------------------

def main():
    print(f"Building stats for season {SEASON}, date {TODAY}", file=sys.stderr)

    # Load rosters
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    # Fetch API data
    print("Fetching player season stats...", file=sys.stderr)
    players_raw = fetch_player_season_stats()

    print("Fetching today's games...", file=sys.stderr)
    games_today = fetch_todays_games()

    print("Fetching standings...", file=sys.stderr)
    standings = fetch_team_standings()

    # Build fast lookup maps
    stats_by_name = {p["Name"].strip(): p for p in players_raw}

    # Opponent map (for today)
    opponents = {}
    for g in games_today:
        home = g["HomeTeam"]
        away = g["AwayTeam"]
        opponents[home] = away
        opponents[away] = home

    # Build standings lookup
    team_info = {}
    for t in standings:
        code = t["Key"]
        team_info[code] = {
            "wins": t.get("Wins", 0),
            "losses": t.get("Losses", 0),
            "win_pct": t.get("Percentage", 0),
            "record_str": f"{t.get('Wins', 0)}-{t.get('Losses', 0)}",
            "streak": t.get("StreakDescription"),
            "points_for": t.get("PointsFor"),
            "points_against": t.get("PointsAgainst"),
            "conf_rank": t.get("ConferenceRank"),
            "div_rank": t.get("DivisionRank")
        }

    # Opponent defensive rank (lower PointsAgainst = better defense)
    sorted_by_def = sorted(standings, key=lambda x: x.get("PointsAgainst", 999))
    def_rank = {team["Key"]: i + 1 for i, team in enumerate(sorted_by_def)}

    # -----------------------------
    # BUILD FINAL OUTPUT
    # -----------------------------

    final = {}
    missing = []

    for team_code, players in rosters.items():
        for name in players:
            raw = stats_by_name.get(name)

            if raw is None:
                # Missing player entry fallback
                missing.append((name, team_code))
                final[name] = {
                    "team": team_code,
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
                    "opponent": None,
                    "def_rank": None,
                    "team_record": None,
                    "team_win_pct": None,
                    "opp_record": None,
                    "opp_win_pct": None,
                    "opp_streak": None,
                }
                continue

            # Opponent
            opp = opponents.get(team_code)

            # Team + Opponent standings
            team_rec = team_info.get(team_code, {})
            opp_rec = team_info.get(opp, {}) if opp else {}

            # Per-game conversions
            games = raw.get("Games", 0)
            g = games if games else 1

            final[name] = {
                "team": team_code,
                "season": SEASON,

                # PER-GAME AVERAGES
                "games": games,
                "min": raw.get("Minutes", 0) / g,
                "pts": raw.get("Points", 0) / g,
                "reb": raw.get("Rebounds", 0) / g,
                "ast": raw.get("Assists", 0) / g,
                "stl": raw.get("Steals", 0) / g,
                "blk": raw.get("BlockedShots", 0) / g,
                "tov": raw.get("Turnovers", 0) / g,

                # Advanced
                "usage": raw.get("UsageRate", 0),
                "pace": raw.get("Possessions", None),

                # Matchups
                "opponent": opp,
                "def_rank": def_rank.get(opp) if opp else None,

                # Team record info
                "team_record": team_rec.get("record_str"),
                "team_win_pct": team_rec.get("win_pct"),

                # Opponent info
                "opp_record": opp_rec.get("record_str"),
                "opp_win_pct": opp_rec.get("win_pct"),
                "opp_streak": opp_rec.get("streak"),
                "opp_points_for": opp_rec.get("points_for"),
                "opp_points_against": opp_rec.get("points_against"),
                "opp_conf_rank": opp_rec.get("conf_rank"),
                "opp_div_rank": opp_rec.get("div_rank"),
            }

    # Save output JSON
    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, sort_keys=True)

    if missing:
        print("\nPlayers not found in SportsData:", file=sys.stderr)
        for n, t in missing:
            print(f" - {n} ({t})", file=sys.stderr)


if __name__ == "__main__":
    main()
