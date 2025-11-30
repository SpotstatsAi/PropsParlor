#!/usr/bin/env python3
"""
build_player_stats_nba.py

Pure NBA.com-based stats builder (no paid APIs).

- Reads:  rosters.json, schedule.json
- Scrapes: NBA.com stats API for league-wide per-game and advanced stats
- Writes: player_stats.json with per-game averages, usage, pace,
          opponent, and opponent defensive rank.

Run locally or in GitHub Actions:
    python scripts/build_player_stats_nba.py
"""

import json
from datetime import datetime, timezone
import sys
import time
import requests

# -----------------------------
# CONFIG
# -----------------------------

# NBA season string in NBA.com format, e.g. "2024-25", "2025-26"
NBA_SEASON = "2025-26"
SEASON_TYPE = "Regular Season"

NBA_STATS_BASE = "https://stats.nba.com/stats"

# Headers so NBA.com actually returns JSON (they block generic bots)
COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "Connection": "keep-alive",
}


# -----------------------------
# NBA FETCH HELPERS
# -----------------------------

def fetch_nba_json(endpoint: str, params: dict) -> dict:
    """
    Call NBA.com stats endpoint and return parsed JSON.
    Handles occasional 429s by backing off briefly.
    """
    url = f"{NBA_STATS_BASE}/{endpoint}"
    for attempt in range(3):
        resp = requests.get(
            url,
            headers=COMMON_HEADERS,
            params=params,
            timeout=30,
        )
        # Simple backoff on rate-limit
        if resp.status_code == 429 and attempt < 2:
            time.sleep(1 + attempt)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()  # last-resort


def resultset_to_dict(json_data: dict, key_field: str) -> dict:
    """
    Convert NBA.com resultSet (headers + rowSet) into a dict
    keyed by `key_field`.
    """
    rs = json_data["resultSets"][0]
    headers = rs["headers"]
    idx = {h: i for i, h in enumerate(headers)}
    out = {}
    for row in rs["rowSet"]:
        key = row[idx[key_field]]
        record = {h: row[idx[h]] for h in headers}
        out[key] = record
    return out


def get_league_player_base() -> dict:
    """
    Per-game base stats for all players.
    Includes: PLAYER_NAME, TEAM_ABBREVIATION, GP, MIN, PTS, REB, AST, STL, BLK, TOV, etc.
    """
    params = {
        "Season": NBA_SEASON,
        "SeasonType": SEASON_TYPE,
        "PerMode": "PerGame",
        "MeasureType": "Base",
        "PlusMinus": "N",
        "PaceAdjust": "N",
        "Rank": "N",
        "Outcome": "",
        "Location": "",
        "SeasonSegment": "",
        "DateFrom": "",
        "DateTo": "",
        "OpponentTeamID": "0",
        "VsConference": "",
        "VsDivision": "",
        "GameSegment": "",
        "Period": "0",
        "ShotClockRange": "",
        "LastNGames": "0",
        "Month": "0",
        "Conference": "",
        "Division": "",
        "GameScope": "",
        "PlayerExperience": "",
        "PlayerPosition": "",
        "StarterBench": "",
        "TwoWay": "0",
        "DraftYear": "",
        "DraftPick": "",
        "College": "",
        "Country": "",
        "Height": "",
        "Weight": "",
        "PORound": "",
    }
    data = fetch_nba_json("leaguedashplayerstats", params)
    return resultset_to_dict(data, "PLAYER_NAME")


def get_league_player_advanced() -> dict:
    """
    Per-game advanced stats for all players.
    Key field: PLAYER_NAME
    Includes USG_PCT, etc.
    """
    params = {
        "Season": NBA_SEASON,
        "SeasonType": SEASON_TYPE,
        "PerMode": "PerGame",
        "MeasureType": "Advanced",
        "PlusMinus": "N",
        "PaceAdjust": "N",
        "Rank": "N",
        "Outcome": "",
        "Location": "",
        "SeasonSegment": "",
        "DateFrom": "",
        "DateTo": "",
        "OpponentTeamID": "0",
        "VsConference": "",
        "VsDivision": "",
        "GameSegment": "",
        "Period": "0",
        "ShotClockRange": "",
        "LastNGames": "0",
        "Month": "0",
        "Conference": "",
        "Division": "",
        "GameScope": "",
        "PlayerExperience": "",
        "PlayerPosition": "",
        "StarterBench": "",
        "TwoWay": "0",
        "DraftYear": "",
        "DraftPick": "",
        "College": "",
        "Country": "",
        "Height": "",
        "Weight": "",
        "PORound": "",
    }
    data = fetch_nba_json("leaguedashplayerstats", params)
    return resultset_to_dict(data, "PLAYER_NAME")


def get_team_advanced() -> dict:
    """
    Team-level advanced stats, including DEF_RATING and PACE.
    Key: TEAM_ABBREVIATION.
    """
    params = {
        "Season": NBA_SEASON,
        "SeasonType": SEASON_TYPE,
        "PerMode": "PerGame",
        "MeasureType": "Advanced",
        "PlusMinus": "N",
        "PaceAdjust": "N",
        "Rank": "N",
        "Outcome": "",
        "Location": "",
        "SeasonSegment": "",
        "DateFrom": "",
        "DateTo": "",
        "OpponentTeamID": "0",
        "VsConference": "",
        "VsDivision": "",
        "GameSegment": "",
        "Period": "0",
        "ShotClockRange": "",
        "LastNGames": "0",
        "Month": "0",
        "Conference": "",
        "Division": "",
        "GameScope": "",
        "PlayerExperience": "",
        "PlayerPosition": "",
        "StarterBench": "",
    }
    data = fetch_nba_json("leaguedashteamstats", params)
    return resultset_to_dict(data, "TEAM_ABBREVIATION")


def build_def_rank(team_adv: dict) -> dict:
    """
    Build opponent defensive rank from DEF_RATING (lower is better).
    Returns: team_abbrev -> rank (1..N)
    """
    rows = list(team_adv.values())
    rows = [r for r in rows if r.get("DEF_RATING") is not None]
    rows.sort(key=lambda r: r["DEF_RATING"])
    rank_map = {}
    for i, r in enumerate(rows, start=1):
        rank_map[r["TEAM_ABBREVIATION"]] = i
    return rank_map


# -----------------------------
# MAIN
# -----------------------------

def main():
    print("Building NBA.com-based player_stats.json...", file=sys.stderr)

    # Load rosters & schedule
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    with open("schedule.json", "r", encoding="utf-8") as f:
        schedule = json.load(f)

    # Today (UTC) as YYYY-MM-DD to match schedule.json keys
    today = datetime.now(timezone.utc).date().isoformat()
    print(f"Using date: {today}", file=sys.stderr)

    todays_games = schedule.get(today, [])
    opponent_map = {}
    for g in todays_games:
        home = g["home_team"]
        away = g["away_team"]
        opponent_map[home] = away
        opponent_map[away] = home

    print(f"Games today: {len(todays_games)}", file=sys.stderr)

    # Fetch league-wide stats from NBA.com
    print("Fetching player base stats from NBA.com...", file=sys.stderr)
    player_base = get_league_player_base()

    print("Fetching player advanced stats from NBA.com...", file=sys.stderr)
    player_adv = get_league_player_advanced()

    print("Fetching team advanced stats from NBA.com...", file=sys.stderr)
    team_adv = get_team_advanced()
    def_rank = build_def_rank(team_adv)

    final = {}
    missing = []

    for team_code, players in rosters.items():
        for name in players:
            base = player_base.get(name)
            adv = player_adv.get(name)

            if not base:
                # Player not found in NBA stats (maybe no games yet)
                missing.append((name, team_code))
                opp = opponent_map.get(team_code)
                final[name] = {
                    "team": team_code,
                    "season": NBA_SEASON,
                    "games": 0,
                    "min": 0.0,
                    "pts": 0.0,
                    "reb": 0.0,
                    "ast": 0.0,
                    "stl": 0.0,
                    "blk": 0.0,
                    "tov": 0.0,
                    "usage": 0.0,
                    "pace": None,
                    "opponent": opp,
                    "def_rank": def_rank.get(opp) if opp else None,
                }
                continue

            gp = base.get("GP", 0) or 0
            min_pg = base.get("MIN", 0.0) or 0.0
            pts_pg = base.get("PTS", 0.0) or 0.0
            reb_pg = base.get("REB", 0.0) or 0.0
            ast_pg = base.get("AST", 0.0) or 0.0
            stl_pg = base.get("STL", 0.0) or 0.0
            blk_pg = base.get("BLK", 0.0) or 0.0
            tov_pg = base.get("TOV", 0.0) or 0.0

            usage = 0.0
            if adv:
                # USG_PCT is already a percent like 24.5
                usage = adv.get("USG_PCT", 0.0) or 0.0

            team_row = team_adv.get(team_code, {})
            pace = team_row.get("PACE")

            opp = opponent_map.get(team_code)
            opp_def_rank = def_rank.get(opp) if opp else None

            final[name] = {
                "team": team_code,
                "season": NBA_SEASON,
                "games": int(gp),
                "min": float(min_pg),
                "pts": float(pts_pg),
                "reb": float(reb_pg),
                "ast": float(ast_pg),
                "stl": float(stl_pg),
                "blk": float(blk_pg),
                "tov": float(tov_pg),
                "usage": float(usage),
                "pace": float(pace) if pace is not None else None,
                "opponent": opp,
                "def_rank": opp_def_rank,
            }

    # Write out JSON
    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, sort_keys=True)

    print(f"Wrote player_stats.json for {len(final)} players", file=sys.stderr)
    if missing:
        print("\nPlayers not found in NBA.com stats:", file=sys.stderr)
        for n, t in missing:
            print(f" - {n} ({t})", file=sys.stderr)


if __name__ == "__main__":
    main()
