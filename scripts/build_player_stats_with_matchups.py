#!/usr/bin/env python3
"""
Builds player_stats.json with:
- SportsData.io full season stats (converted to per-game averages)
- Opponent for today's games
- Team defensive ranks (via PointsAgainst)
- Proxy usage% (SportsData does NOT provide true USG%)
- Basic pace metrics where available
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
    headers = {"Ocp-Apim-Subscription-Key": API_KEY}
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    return resp.json()


def fetch_player_season_stats(season):
    url = f"{BASE_STATS_URL}/PlayerSeasonStats/{season}?key={API_KEY}"
    return fetch_json(url)


def fetch_todays_games():
    url = f"{BASE_SCORES_URL}/GamesByDate/{TODAY}?key={API_KEY}"
    return fetch_json(url)


def get_team_stats():
    """
    Build defensive ranks using Standings → PointsAgainst.
    Lower PointsAgainst = better defense
    """
    url = f"{BASE_SCORES_URL}/Standings/{SEASON}?key={API_KEY}"
    data = fetch_json(url)

    sorted_by_def = sorted(data, key=lambda t: t.get("PointsAgainst", 999))
    ranks = {}

    rank = 1
    for team in sorted_by_def:
        code = team["Key"]
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

    # Load rosters.json
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    # Fetch season stats
    print("Fetching player season stats from SportsData...", file=sys.stderr)
    season_stats = fetch_player_season_stats(SEASON)

    # Games today
    print("Fetching today's games...", file=sys.stderr)
    todays_games = fetch_todays_games()

    # Team defensive ranks
    print("Fetching team defensive metrics...", file=sys.stderr)
    team_def = get_team_stats()

    # Map raw data by name
    raw_by_name = {p["Name"].strip(): p for p in season_stats}

    # Opponent mapping
    opponent_map = {}
    for g in todays_games:
        home, away = g["HomeTeam"], g["AwayTeam"]
        opponent_map[home] = away
        opponent_map[away] = home

    # -------- BUILD USAGE PROXY BASED ON TEAM TOTALS --------
    team_usage_total = {}

    for p in season_stats:
        team = p.get("Team", "")
        if not team:
            continue

        fga = p.get("FieldGoalsAttempted", 0)
        fta = p.get("FreeThrowsAttempted", 0)
        tov = p.get("Turnovers", 0)

        # Scoring opportunities proxy
        usage_score = (fga * 2) + (fta * 0.44) + tov

        team_usage_total.setdefault(team, 0)
        team_usage_total[team] += usage_score

    # -----------------------------
    # BUILD FINAL STRUCTURE
    # -----------------------------

    final = {}
    missing = []

    for team_code, players in rosters.items():
        for name in players:

            raw = raw_by_name.get(name)
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

            games = raw.get("Games", 0) or 1

            # Convert TOTALS → PER-GAME averages
            pts = raw.get("Points", 0) / games
            reb = raw.get("Rebounds", 0) / games
            ast = raw.get("Assists", 0) / games
            stl = raw.get("Steals", 0) / games
            blk = raw.get("BlockedShots", 0) / games
            tov = raw.get("Turnovers", 0) / games

            fga = raw.get("FieldGoalsAttempted", 0) / games
            fg3a = raw.get("ThreePointersAttempted", 0) / games
            fta = raw.get("FreeThrowsAttempted", 0) / games

            fg_pct = raw.get("FieldGoalsPercentage", 0)
            fg3_pct = raw.get("ThreePointersPercentage", 0)
            ft_pct = raw.get("FreeThrowsPercentage", 0)

            # Usage proxy
            player_usage_score = (fga * 2) + (fta * 0.44) + tov
            team_total = team_usage_total.get(team_code, 1)
            usage_pct = (player_usage_score / team_total) * 100

            # Opponent + def rank
            opp = opponent_map.get(team_code)
            def_rank = team_def.get(opp, {}).get("DefRank") if opp else None

            final[name] = {
                "team": team_code,
                "season": SEASON,
                "games": games,
                "min": raw.get("Minutes", 0),

                # Per-game stats
                "pts": round(pts, 1),
                "reb": round(reb, 1),
                "ast": round(ast, 1),
                "stl": round(stl, 1),
                "blk": round(blk, 1),
                "tov": round(tov, 1),

                # Shooting & attempts
                "fga": round(fga, 1),
                "fg3a": round(fg3a, 1),
                "fta": round(fta, 1),
                "fg_pct": fg_pct,
                "fg3_pct": fg3_pct,
                "ft_pct": ft_pct,

                # Advanced
                "usage": round(usage_pct, 1),
                "pace": raw.get("Possessions", None),

                # Opponent matchup
                "opponent": opp,
                "def_rank": def_rank,
            }

    # Output file
    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, sort_keys=True)

    if missing:
        print("\nPlayers not found in SportsData:", file=sys.stderr)
        for n, t in missing:
            print(f" - {n} ({t})", file=sys.stderr)


if __name__ == "__main__":
    main()
