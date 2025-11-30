#!/usr/bin/env python3
"""
Enhanced player_stats.json generator:

Adds:
- Opponent
- Opponent defensive rank
- Usage + Pace
- Team record + opponent record
- Opponent streak, rank, points for/against

Fully compatible with SportsData.io and your UI.
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

SEASON = 2025                # 2025–26 NBA season
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

BASE_STATS_URL = "https://api.sportsdata.io/v3/nba/stats/json"
BASE_SCORES_URL = "https://api.sportsdata.io/v3/nba/scores/json"


# -----------------------------
# FETCH HELPERS
# -----------------------------

def fetch_json(url):
    headers = {"Ocp-Apim-Subscription-Key": API_KEY}
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    return resp.json()


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
# BEGIN MAIN
# -----------------------------

def main():
    print(f"Building stats for season {SEASON}, date {TODAY}", file=sys.stderr)

    # Load rosters
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    # Fetch SportsData
    print("Fetching player season stats...", file=sys.stderr)
    season_stats = fetch_player_season_stats()

    print("Fetching today's games...", file=sys.stderr)
    todays_games = fetch_todays_games()

    print("Fetching standings...", file=sys.stderr)
    standings = fetch_team_standings()

    # ----------------------------
    # Build lookup dictionaries
    # ----------------------------

    # Player stats lookup
    stats_by_name = {p["Name"].strip(): p for p in season_stats}

    # Opponent lookup for today
    opponents = {}
    for g in todays_games:
        home = g["HomeTeam"]
        away = g["AwayTeam"]
        opponents[home] = away
        opponents[away] = home

    # Team standings lookup
    team_info = {}
    for t in standings:
        code = t["Key"]
        wins = t.get("Wins", 0)
        losses = t.get("Losses", 0)
        streak = t.get("StreakDescription", "")

        team_info[code] = {
            "wins": wins,
            "losses": losses,
            "win_pct": t.get("Percentage", 0),
            "record_str": f"{wins}-{losses}",
            "streak": streak,
            "points_for": t.get("PointsFor"),
            "points_against": t.get("PointsAgainst"),
            "conf_rank": t.get("ConferenceRank"),
            "div_rank": t.get("DivisionRank"),
        }

    # Opponent defense rank (sort by PointsAgainst)
    sorted_by_def = sorted(standings, key=lambda x: x.get("PointsAgainst", 999))
    def_rank = {t["Key"]: i+1 for i, t in enumerate(sorted_by_def)}

    # ----------------------------
    # BUILD FINAL OUTPUT
    # ----------------------------

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

            # Team + Opponent record
            team_rec = team_info.get(team_code, {})
            opp_rec = team_info.get(opp, {}) if opp else {}

            final[name] = {
                "team": team_code,
                "season": SEASON,

                # Player stats
                "games": raw.get("Games", 0),
                "min": raw.get("Minutes", 0),
                "pts": raw.get("Points", 0),
                "reb": raw.get("Rebounds", 0),
                "ast": raw.get("Assists", 0),
                "stl": raw.get("Steals", 0),
                "blk": raw.get("BlockedShots", 0),
                "tov": raw.get("Turnovers", 0),

                # Advanced
                "usage": raw.get("UsageRate", 0),
                "pace": raw.get("Possessions", None),

                # Matchups
                "opponent": opp,
                "def_rank": def_rank.get(opp) if opp else None,

                # NEW — Team record and opponent record
                "team_record": team_rec.get("record_str"),
                "team_win_pct": team_rec.get("win_pct"),

                "opp_record": opp_rec.get("record_str"),
                "opp_win_pct": opp_rec.get("win_pct"),
                "opp_streak": opp_rec.get("streak"),
                "opp_points_for": opp_rec.get("points_for"),
                "opp_points_against": opp_rec.get("points_against"),
                "opp_conf_rank": opp_rec.get("conf_rank"),
                "opp_div_rank": opp_rec.get("div_rank"),
            }

    # Write output
    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, sort_keys=True)

    # Missing players
    if missing:
        print("\nPlayers not found:", file=sys.stderr)
        for n, t in missing:
            print(f" - {n} ({t})", file=sys.stderr)


if __name__ == "__main__":
    main()
