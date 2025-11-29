#!/usr/bin/env python3
"""
Build player_stats.json using SportsData.io + matchup difficulty.

Requirements:
- rosters.json (your existing team → [players] mapping)
- schedule.json (keyed by YYYY-MM-DD with games, as used in the UI)

Outputs:
- player_stats.json with per-player season stats + opponent matchup fields:
  - opponent_team
  - opponent_defense_score (0-100, higher = tougher defense)
  - opponent_defense_tier: "green", "yellow", or "red"
"""

import os
import json
import datetime
import requests

# ================== CONFIG ==================

API_KEY = os.getenv("SPORTSDATA_API_KEY", "61d3779041f44f37bd511dbe1c70e84e")  # replace or use env
SEASON = 2026  # 2025-26 season

# Stats endpoints
STATS_BASE = "https://api.sportsdata.io/v3/nba/stats/json"
SCORES_BASE = "https://api.sportsdata.io/v3/nba/scores/json"

ROSTERS_FILE = "rosters.json"
SCHEDULE_FILE = "schedule.json"
OUTPUT_FILE = "player_stats.json"

# Team alias handling (if any)
TEAM_ALIASES = {
    # If you ever need mapping, e.g.:
    # "BKN": "BRK",
}

# ================== HTTP HELPERS ==================

def fetch_json(url, params=None):
    if params is None:
        params = {}
    params["key"] = API_KEY

    resp = requests.get(url, params=params, timeout=40)
    resp.raise_for_status()
    return resp.json()


# ================== DATA LOADERS ==================

def load_rosters():
    with open(ROSTERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schedule_for_today():
    """
    Returns list of today's games from schedule.json using local date (YYYY-MM-DD),
    and a mapping { team_code: opponent_team_code }.
    """
    today = datetime.date.today().isoformat()

    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            sched = json.load(f)
    except FileNotFoundError:
        print("schedule.json not found; skipping matchup mapping.")
        return today, [], {}

    games = sched.get(today, [])

    opponent_map = {}
    for g in games:
        home = g.get("home_team")
        away = g.get("away_team")
        if not home or not away:
            continue
        opponent_map[home] = away
        opponent_map[away] = home

    return today, games, opponent_map


# ================== SPORTS DATA FETCHERS ==================

def fetch_player_season_stats(season: int):
    # SportsData uses the first year of the season (2025 for 2025-26)
    sd_season = season - 1  

    url = (
        f"https://api.sportsdata.io/v3/nba/stats/json/"
        f"PlayerSeasonStats/{sd_season}?key={API_KEY}"
    )

    print(f"Fetching player season stats for SportsData season {sd_season}...")
    return fetch_json(url)



def fetch_team_season_stats(season: int):
    """
    Uses SportsData.io TeamSeasonStats endpoint.

    Docs pattern (adjust if needed):
    GET /v3/nba/scores/json/TeamSeasonStats/{season}

    We will use an opponent-based defensive metric such as:
        OpponentPointsPerGame
    If the key name differs, adjust inside build_team_defense_table().
    """
    url = f"{SCORES_BASE}/TeamSeasonStats/{season}"
    print(f"Fetching team season stats for {season}...")
    return fetch_json(url)


# ================== TRANSFORMS ==================

def build_team_defense_table(team_stats):
    """
    Build a dict: { Team: { 'def_metric': float, 'rank': int, 'score_0_100': float, 'tier': str } }

    def_metric is lower = better defense (e.g., OpponentPointsPerGame).
    score_0_100 is normalized so 100 = toughest defense, 0 = softest.
    """
    # Extract raw defensive metric
    metrics = []
    for t in team_stats:
        # SportsData common fields: "Team", "OpponentPointsPerGame", etc.
        # If this KeyError triggers, inspect one sample object and fix the key name.
        team = t.get("Team")
        if not team:
            continue

        # ---- IMPORTANT: adjust this field name if different in your JSON ----
        raw = t.get("OpponentPointsPerGame")
        # ----------------------------------------------------------------------
        if raw is None:
            # fallback to PointsAllowedPerGame or other, if needed
            raw = t.get("PointsAllowedPerGame")

        if raw is None:
            continue

        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue

        metrics.append((team, val))

    if not metrics:
        print("No opponent defensive metric found; defense table will be empty.")
        return {}

    # Rank by def_metric ascending (lower points allowed = better defense)
    metrics.sort(key=lambda x: x[1])  # [(team, metric), ...]
    teams_sorted = [m[0] for m in metrics]
    values = [m[1] for m in metrics]

    v_min = min(values)
    v_max = max(values)
    spread = max(v_max - v_min, 1e-6)

    defense_table = {}

    for rank, (team, val) in enumerate(metrics, start=1):
        # 0..1: (val - v_min) / spread, but lower val = better
        # So we invert: tougher defense (lower val) => higher normalized.
        normalized = 1.0 - (val - v_min) / spread
        score_0_100 = round(normalized * 100, 2)

        # Tiering: you can tweak thresholds
        if score_0_100 >= 66:
            tier = "red"      # very tough D
        elif score_0_100 >= 33:
            tier = "yellow"   # neutral/medium
        else:
            tier = "green"    # soft defense

        defense_table[team] = {
            "def_metric": val,
            "rank": rank,
            "score_0_100": score_0_100,
            "tier": tier,
        }

    return defense_table


def normalize_team_code(code: str) -> str:
    if not code:
        return ""
    return TEAM_ALIASES.get(code, code)


def build_player_stats(rosters, player_stats_raw, defense_table, opponent_map):
    """
    Build final player_stats.json structure:
    {
      "Player Name": {
          "team": "BOS",
          "season": 2026,
          "games": ...,
          "min": ...,
          "pts": ...,
          ...
          "usage": ... (if available)
          "opponent_team": "PHI" or null,
          "opponent_defense_score": float or null,
          "opponent_defense_tier": "green"/"yellow"/"red" or null
      },
      ...
    }
    """
    # Build quick lookup for player stats from SportsData
    # SportsData PlayerSeasonStats objects typically have fields:
    #   "Name", "Team", "Games", "Minutes", "Points", "Rebounds", "Assists",
    #   "Steals", "BlockedShots", "Turnovers", "ThreePointAttempts", "ThreePointersMade",
    #   "FreeThrowAttempts", "FreeThrowsMade", "FieldGoalsAttempted", "FieldGoalsMade",
    #   "UsageRate", etc.
    player_lookup = {}
    for p in player_stats_raw:
        name = p.get("Name")
        if not name:
            continue
        player_lookup[name] = p

    final = {}

    for team_code, players in rosters.items():
        norm_team = normalize_team_code(team_code)
        opp_team = opponent_map.get(team_code)  # preserve your codes in schedule.json
        norm_opp_team = normalize_team_code(opp_team) if opp_team else None

        defense_info = defense_table.get(norm_opp_team) if norm_opp_team else None

        for name in players:
            pdata = player_lookup.get(name)
            if pdata is None:
                # Player not in SportsData feed – fallback zeros.
                stats = {
                    "games": 0,
                    "min": 0.0,
                    "pts": 0.0,
                    "reb": 0.0,
                    "ast": 0.0,
                    "stl": 0.0,
                    "blk": 0.0,
                    "tov": 0.0,
                    "fg3a": 0.0,
                    "fg3_pct": 0.0,
                    "fga": 0.0,
                    "fg_pct": 0.0,
                    "fta": 0.0,
                    "ft_pct": 0.0,
                    "usage": 0.0,
                }
            else:
                # Map SportsData fields to your schema; adjust field names as needed.
                games = pdata.get("Games", 0)
                minutes = pdata.get("Minutes", 0.0)
                pts = pdata.get("Points", 0.0)
                reb = pdata.get("Rebounds", 0.0)
                ast = pdata.get("Assists", 0.0)
                stl = pdata.get("Steals", 0.0)
                blk = pdata.get("BlockedShots", 0.0)
                tov = pdata.get("Turnovers", 0.0)

                fg3a = pdata.get("ThreePointAttempts", 0.0)
                fg3m = pdata.get("ThreePointersMade", 0.0)
                fga = pdata.get("FieldGoalsAttempted", 0.0)
                fgm = pdata.get("FieldGoalsMade", 0.0)
                fta = pdata.get("FreeThrowAttempts", 0.0)
                ftm = pdata.get("FreeThrowsMade", 0.0)

                usage = pdata.get("UsageRate", 0.0)

                def pct(made, att):
                    try:
                        att_val = float(att)
                        if att_val <= 0:
                            return 0.0
                        return round(float(made) / att_val, 3)
                    except (TypeError, ValueError):
                        return 0.0

                stats = {
                    "games": games or 0,
                    "min": minutes or 0.0,
                    "pts": pts or 0.0,
                    "reb": reb or 0.0,
                    "ast": ast or 0.0,
                    "stl": stl or 0.0,
                    "blk": blk or 0.0,
                    "tov": tov or 0.0,
                    "fg3a": fg3a or 0.0,
                    "fg3_pct": pct(fg3m, fg3a),
                    "fga": fga or 0.0,
                    "fg_pct": pct(fgm, fga),
                    "fta": fta or 0.0,
                    "ft_pct": pct(ftm, fta),
                    "usage": usage or 0.0,
                }

            out = dict(stats)
            out.update({
                "team": team_code,
                "season": SEASON,
                "opponent_team": opp_team,
                "opponent_defense_score": (
                    defense_info["score_0_100"] if defense_info else None
                ),
                "opponent_defense_tier": (
                    defense_info["tier"] if defense_info else None
                ),
            })

            final[name] = out

    return final


# ================== MAIN ==================

def main():
    rosters = load_rosters()
    today_str, games_today, opponent_map = load_schedule_for_today()

    print(f"Building stats for season {SEASON}, date {today_str}")
    if games_today:
        print(f"Games today: {len(games_today)}")
    else:
        print("No games found for today in schedule.json; opponent fields will be None.")

    player_raw = fetch_player_season_stats(SEASON)
    team_stats = fetch_team_season_stats(SEASON)
    defense_table = build_team_defense_table(team_stats)

    final_stats = build_player_stats(rosters, player_raw, defense_table, opponent_map)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_stats, f, indent=2, sort_keys=True)

    print(f"Wrote {len(final_stats)} players to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
