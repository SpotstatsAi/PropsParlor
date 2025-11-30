#!/usr/bin/env python3
"""
FREE-TIER COMPATIBLE HYBRID STATS ENGINE
NO Standings endpoint.
Team records + defense ranking are computed manually
from SeasonGames (FREE endpoint).
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

YEAR = 2025
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
YESTERDAY = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

SCORES = "https://api.sportsdata.io/v3/nba/scores/json"
STATS = "https://api.sportsdata.io/v3/nba/stats/json"

HEADERS = {"Ocp-Apim-Subscription-Key": API_KEY}

def fetch_json(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()

def get_season_games():
    url = f"{SCORES}/Games/{YEAR}?key={API_KEY}"
    return fetch_json(url)

def get_todays_games():
    url = f"{SCORES}/GamesByDate/{TODAY}?key={API_KEY}"
    return fetch_json(url)

def get_team_season_stats(team):
    url = f"{STATS}/PlayerSeasonStatsByTeam/{YEAR}/{team}?key={API_KEY}"
    return fetch_json(url)

def get_game_logs(date):
    url = f"{STATS}/PlayerGameStatsByDate/{date}?key={API_KEY}"
    return fetch_json(url)

def build_team_standings(games):
    wins = defaultdict(int)
    losses = defaultdict(int)
    pf = defaultdict(int)
    pa = defaultdict(int)
    last_game = {}

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
            last_game[home] = "W"
            last_game[away] = "L"
        else:
            wins[away] += 1
            losses[home] += 1
            last_game[away] = "W"
            last_game[home] = "L"

    teams = set(list(wins.keys()) + list(losses.keys()))
    standings = {}

    # compute streaks
    streak = defaultdict(int)
    prev = None
    for t in teams:
        streak[t] = 0
        prev = last_game.get(t)
        if prev == "W":
            streak[t] = 1
        elif prev == "L":
            streak[t] = -1

    for t in teams:
        w = wins[t]
        l = losses[t]
        pct = w / (w + l) if (w + l) > 0 else 0

        standings[t] = {
            "wins": w,
            "losses": l,
            "win_pct": pct,
            "record_str": f"{w}-{l}",
            "streak": f"{'W' if streak[t]>0 else 'L'}{abs(streak[t])}" if streak[t] != 0 else "N/A",
            "points_for": pf[t],
            "points_against": pa[t],
        }

    return standings

def main():
    print("Building FREE-TIER hybrid stats...", file=sys.stderr)

    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    print("Fetching season games (FREE)...", file=sys.stderr)
    season_games = get_season_games()

    standings = build_team_standings(season_games)

    print("Fetching today’s games...", file=sys.stderr)
    todays = get_todays_games()

    opponent_map = {}
    for g in todays:
        opponent_map[g["HomeTeam"]] = g["AwayTeam"]
        opponent_map[g["AwayTeam"]] = g["HomeTeam"]

    print("Fetching logs...", file=sys.stderr)
    try:
        today_logs = get_game_logs(TODAY)
    except:
        today_logs = []
    try:
        yesterday_logs = get_game_logs(YESTERDAY)
    except:
        yesterday_logs = []

    logs_by_player = {lg["Name"].strip(): lg for lg in (today_logs + yesterday_logs)}

    final = {}
    missing = []

    # DEFENSE RANK (lower PA = better defense)
    sorted_by_def = sorted(standings.items(), key=lambda x: x[1]["points_against"])
    def_rank = {team: i+1 for i, (team, _) in enumerate(sorted_by_def)}

    for team, players in rosters.items():
        try:
            season_stats = get_team_season_stats(team)
        except:
            season_stats = []

        szn_map = {p["Name"].strip(): p for p in season_stats}

        for name in players:
            raw = szn_map.get(name)
            opp = opponent_map.get(team)
            opp_info = standings.get(opp, {}) if opp else {}

            if raw is None:
                missing.append((name, team))
                final[name] = {
                    "team": team,
                    "games": 0,
                    "pts": 0,
                    "reb": 0,
                    "ast": 0,
                    "stl": 0,
                    "blk": 0,
                    "tov": 0,
                    "usage": 0,
                    "pace": None,
                    "opponent": opp,
                    "def_rank": def_rank.get(opp),
                    "team_record": standings.get(team, {}).get("record_str"),
                    "opp_record": opp_info.get("record_str"),
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

                "opp_record": opp_info.get("record_str"),
                "opp_win_pct": opp_info.get("win_pct"),
                "opp_streak": opp_info.get("streak"),
                "opp_points_for": opp_info.get("points_for"),
                "opp_points_against": opp_info.get("points_against"),
            }

            if name in logs_by_player:
                lg = logs_by_player[name]
                final[name]["today_pts"] = lg.get("Points", 0)

    with open("player_stats.json", "w") as f:
        json.dump(final, f, indent=2)

    print("DONE — free-tier hybrid stats built!", file=sys.stderr)

if __name__ == "__main__":
    main()
