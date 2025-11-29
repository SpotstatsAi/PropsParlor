#!/usr/bin/env python3
"""
Pulls current-season stats from Basketball Reference and writes player_stats.json
to match what app.js expects:

- Top-level object keyed by full player name (exactly as in rosters.json)
- Each value is a stats object with fields like:
  pts, reb, ast, stl, blk, tov, min, fg3a, fg3_pct, fga, fg_pct, fta, ft_pct,
  games, usage, team, season, pace, foul_difficulty, blowout_risk
"""

import json
import sys
from typing import Dict, Tuple

import requests
from bs4 import BeautifulSoup

# ===== CONFIG =====
# Season end year. Your 2025–26 season is "2026" on Basketball Reference.
YEAR = 2026

PER_GAME_URL = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_per_game.html"
ADV_URL = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_advanced.html"

# Map your team codes -> Basketball Reference team codes
TEAM_ALIASES = {
    "BKN": "BRK",
    "CHA": "CHO",
    "PHX": "PHO",
    # UTA is already "UTA" on BR
    # Add more here if you ever need them
}


def to_bref_team(team_code: str) -> str:
    return TEAM_ALIASES.get(team_code, team_code)


def fetch_table_rows(url: str, table_id: str):
    """Download a Basketball Reference table and return all <tr> rows from its <tbody>."""
    print(f"Fetching {url}", file=sys.stderr)
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (SpotstatsAi scraper)"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", id=table_id)
    if table is None:
        raise RuntimeError(f"Could not find table with id={table_id} at {url}")
    tbody = table.find("tbody")
    return tbody.find_all("tr")


def parse_per_game():
    """
    Returns:
      per_by_name_team: dict[(player_name, team_code)] -> per-game stats dict
      tot_by_name:      dict[player_name]              -> 'TOT' per-game stats dict
    """
    rows = fetch_table_rows(PER_GAME_URL, "per_game_stats")
    per_by_name_team: Dict[Tuple[str, str], dict] = {}
    tot_by_name: Dict[str, dict] = {}

    def get_float(row, stat):
        cell = row.find("td", {"data-stat": stat})
        txt = cell.get_text(strip=True) if cell else ""
        if txt in ("", "NA"):
            return None
        try:
            return float(txt)
        except ValueError:
            return None

    def get_int(row, stat):
        cell = row.find("td", {"data-stat": stat})
        txt = cell.get_text(strip=True) if cell else ""
        if not txt:
            return None
        try:
            return int(txt)
        except ValueError:
            return None

    for row in rows:
        # skip header sub-rows
        if row.get("class") and "thead" in row["class"]:
            continue

        player_cell = row.find("td", {"data-stat": "player"})
        if player_cell is None:
            continue

        name = player_cell.get_text(strip=True)
        team = row.find("td", {"data-stat": "team_id"}).get_text(strip=True)

        record = {
            "games": get_int(row, "g") or 0,
            "min": get_float(row, "mp_per_g") or 0.0,
            "pts": get_float(row, "pts_per_g") or 0.0,
            "reb": get_float(row, "trb_per_g") or 0.0,
            "ast": get_float(row, "ast_per_g") or 0.0,
            "stl": get_float(row, "stl_per_g") or 0.0,
            "blk": get_float(row, "blk_per_g") or 0.0,
            "tov": get_float(row, "tov_per_g") or 0.0,
            "fg3a": get_float(row, "fg3a_per_g") or 0.0,
            "fg3_pct": get_float(row, "fg3_pct") or 0.0,
            "fga": get_float(row, "fga_per_g") or 0.0,
            "fg_pct": get_float(row, "fg_pct") or 0.0,
            "fta": get_float(row, "fta_per_g") or 0.0,
            "ft_pct": get_float(row, "ft_pct") or 0.0,
        }

        if team == "TOT":
            tot_by_name[name] = record
        else:
            per_by_name_team[(name, team)] = record

    return per_by_name_team, tot_by_name


def parse_advanced_usage():
    """
    Returns:
      usage_by_name: dict[player_name] -> USG% (float, e.g. 24.5)
    Uses the 'TOT' row when present for that player.
    """
    rows = fetch_table_rows(ADV_URL, "advanced_stats")
    usage_by_name: Dict[str, float] = {}

    def get_float(row, stat):
        cell = row.find("td", {"data-stat": stat})
        txt = cell.get_text(strip=True) if cell else ""
        if txt in ("", "NA"):
            return None
        try:
            return float(txt)
        except ValueError:
            return None

    for row in rows:
        if row.get("class") and "thead" in row["class"]:
            continue

        player_cell = row.find("td", {"data-stat": "player"})
        if player_cell is None:
            continue

        name = player_cell.get_text(strip=True)
        team = row.find("td", {"data-stat": "team_id"}).get_text(strip=True)
        usg = get_float(row, "usg_pct")
        if usg is None:
            continue

        # Prefer the combined 'TOT' row, it's closest to season-long usage
        if team == "TOT":
            usage_by_name[name] = usg
        else:
            # If there's no TOT row, team row is still fine
            usage_by_name.setdefault(name, usg)

    return usage_by_name


def main():
    # 1) Load rosters.json so we only keep players you care about
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    per_by_name_team, tot_by_name = parse_per_game()
    usage_by_name = parse_advanced_usage()

    result = {}
    missing = []

    for team_code, players in rosters.items():
        bref_team = to_bref_team(team_code)

        for name in players:
            # Try to match the (name, team) row first
            stats = per_by_name_team.get((name, bref_team))

            # If no team-specific row, fall back to 'TOT'
            if stats is None:
                stats = tot_by_name.get(name)

            if stats is None:
                # Not found at all – create a neutral entry so app.js doesn't break
                missing.append((name, team_code))
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
                }

            out = dict(stats)
            out.update(
                {
                    "team": team_code,
                    "season": YEAR,
                    # If usage is missing, just set 0 so the scorePlayer formula is neutral
                    "usage": usage_by_name.get(name, 0.0),
                    # These you can refine later; keep neutral for now
                    "pace": None,
                    "foul_difficulty": None,
                    "blowout_risk": None,
                }
            )

            # Final key in player_stats.json is the full name string (must match rosters.json)
            result[name] = out

    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)

    if missing:
        print("Players not found on Basketball Reference:", file=sys.stderr)
        for name, team_code in sorted(missing):
            print(f" - {name} ({team_code})", file=sys.stderr)


if __name__ == "__main__":
    main()
