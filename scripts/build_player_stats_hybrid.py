#!/usr/bin/env python3
"""
FREE-TIER NBA HYBRID ENGINE
---------------------------------
Builds:
- Season averages (per-game)
- Opponent for today
- Opponent defense ranking
- Team record, win%, streak, PF/PA
WITHOUT using Standings or SeasonGames endpoints.

It reconstructs the entire season by calling
/GamesByDate for every date from season start → today.
"""

import json
import os
import sys
from datetime import datetime, timedelta
import requests
from collections import defaultdict

API_KEY = os.getenv("SPORTSDATA_API_KEY", "").strip()
if not API_KEY:
    print("ERROR: SPORTSDATA_API_KEY missing!", file=sys.stderr)
    sys.exit(1)

YEAR = 2025  # 2025–26 season
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

SCORES = "https://api.sportsdata.io/v3/nba/scores/json"
STATS  = "https://api.sportsdata.io/v3/nba/stats/json"

HEADERS = {"Ocp-Apim-Subscription-Key": API_KEY}

SEASON_START = datetime(2025, 10, 1)   # Opening week
SEASON_END   = datetime.utcnow()


def fetch_json(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_season_games_free():
    """Rebuild entire season via GamesByDate — FREE TIER SAFE."""
    print("Rebuilding entire NBA season from daily data…", file=sys.stderr)

    games = []
    day = SEASON_START

    while day <= SEASON_END:
        date_str = day.strftime("%Y-%m-%d")
        try:
            url = f"{SCORES}/GamesByDate/{date_str}?key={API_KEY}"
            daily = fetch_json(url)
            games.extend(daily)
        except:
            pass
        day += timedelta(days=1)

    return games


def get_todays_games():
    url = f"{SCORES}/GamesByDate/{TODAY}?key={API_KEY}"
    return fetch_json(url)


def get_team_player_stats(team):
    url = f"{STATS}/PlayerSeasonStatsByTeam/{YEAR}/{team}?key={API_KEY}"
    return fetch_json(url)


def get_player_logs(date):
    url = f"{STATS}/PlayerGameStatsByDate/{date}?key={API_KEY}"
    try:
        return fetch_json(url)
    except:
        return []


def build_standings(games):
    """Build standings manually using daily game results."""
    wins = defaultdict(int)
    losses = defaultdict(int)
    pf = defaultdict(int)
    pa = defaultdict(int)
    last_result = {}

    for g in games:
        if g.get("Status") != "Final":
            continue

        home = g["HomeTeam"]
        away = g["AwayTeam"]
        hs = g["HomeTeamScore"] or 0
        as_ = g["AwayTeamScore"] or 0

        pf[home] += hs
        pa[home] += as_
        pf[away] += as_
        pa[away] += hs

        if hs > as_:
            wins[home] += 1
            losses[away] += 1
            last_result[home] = "W"
            last_result[away] = "L"
        else:
            wins[away] += 1
            losses[home] += 1
            last_result[away] = "W"
            last_result[home] = "L"

    standings = {}
    for team in set(list(wins.keys()) + list(losses.keys())):
        w = wins[team]
        l = losses[team]
        pct = w / (w + l) if (w + l) else 0
        streak = last_result.get(team)
        streak_val = f"{streak}1" if streak else "N/A"

        standings[team] = {
            "wins": w,
            "losses": l,
            "win_pct": pct,
            "record_str": f"{w}-{l}",
            "streak": streak_val,
            "points_for": pf[team],
            "points_against": pa[team],
        }

    return standings


def main():
    print("Building FREE-TIER hybrid stats...", file=sys.stderr)

    with open("rosters.json", "r") as f:
        rosters = json.load(f)

    print("Gathering season games (FREE)…", file=sys.stderr)
    season_games = get_season_games_free()

    print("Building standings…", file=sys.stderr)
    standings = build_standings(season_games)

    print("Fetching today's games…", file=sys.stderr)
    todays = get_todays_games()

    opponent_map = {}
    for g in todays:
        opponent_map[g["HomeTeam"]] = g["AwayTeam"]
        opponent_map[g["AwayTeam"]] = g["HomeTeam"]

    print("Fetching logs…", file=sys.stderr)
    logs_today = get_player_logs(TODAY)
    logs_yesterday = get_player_logs(
        (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    )

    logs_map = {lg["Name"].strip(): lg for lg in (logs_today + logs_yesterday)}

    final = {}
    missing = []

    sorted_def = sorted(standings.items(), key=lambda x: x[1]["points_against"])
    def_rank = {team: i + 1 for i, (team, _) in enumerate(sorted_def)}

    for team, players in rosters.items():
        try:
            team_stats = get_team_player_stats(team)
            team_stats_map = {p["Name"].strip(): p for p in team_stats}
        except:
            team_stats_map = {}

        for name in players:
            raw = team_stats_map.get(name)
            opp = opponent_map.get(team)
            opp_inf = standings.get(opp, {})

            if raw is None:
                missing.append((name, team))
                final[name] = {
                    "team": team,
                    "pts": 0,
                    "reb": 0,
                    "ast": 0,
                    "games": 0,
                    "opponent": opp,
                    "def_rank": def_rank.get(opp),
                    "team_record": standings.get(team, {}).get("record_str"),
                    "opp_record": opp_inf.get("record_str"),
                }
                continue

            g = raw.get("Games", 0) or 1

            final[name] = {
                "team": team,
                "games": g,
                "pts": raw["Points"] / g,
                "reb": raw["Rebounds"] / g,
                "ast": raw["Assists"] / g,
                "stl": raw["Steals"] / g,
                "blk": raw["BlockedShots"] / g,
                "tov": raw["Turnovers"] / g,
                "min": raw["Minutes"] / g,
                "usage": 0,
                "pace": None,

                "opponent": opp,
                "def_rank": def_rank.get(opp),

                "team_record": standings.get(team, {}).get("record_str"),
                "team_win_pct": standings.get(team, {}).get("win_pct"),

                "opp_record": opp_inf.get("record_str"),
                "opp_win_pct": opp_inf.get("win_pct"),
                "opp_streak": opp_inf.get("streak"),

                "today_pts": logs_map.get(name, {}).get("Points"),
            }

    with open("player_stats.json", "w") as f:
        json.dump(final, f, indent=2)

    print("DONE — FREE-TIER hybrid stats built!", file=sys.stderr)


if __name__ == "__main__":
    main()
