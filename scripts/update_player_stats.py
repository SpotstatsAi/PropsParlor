#!/usr/bin/env python3
"""
Pulls current-season stats from Basketball Reference (via your Cloudflare Worker)
and writes player_stats.json in the format app.js expects.

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
from urllib.parse import quote

# ===== CONFIG =====
# Season end year. Your 2025–26 season is "2026" on Basketball Reference.
YEAR = 2026

# Basketball Reference pages
PER_GAME_URL = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_per_game.html"
ADV_URL      = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_advanced.html"

# Your Cloudflare Worker base URL (the one that's working in your browser)
PROXY_BASE = "https://bbr-proxy.dblair1027.workers.dev"

# Map your team codes -> Basketball Reference team codes
TEAM_ALIASES = {
    "BKN": "BRK",
    "CHA": "CHO",
    "PHX": "PHO",
    # UTA is already "UTA" on BR
    # Add more here if you ever need them
}


def to_bref_team(team_code: str) -> str:
    """Translate your team code to Basketball Reference's code if needed."""
    return TEAM_ALIASES.get(team_code, team_code)


def fetch_html_via_proxy(url: str) -> str:
    """
    Hit your Cloudflare Worker, which then fetches Basketball Reference.

    We pass the BR URL as a query parameter:
    https://bbr-proxy.../?url=<encoded real url>
    """
    proxied = f"{PROXY_BASE}/?url={quote(url, safe='')}"
    print(f"Fetching via proxy: {proxied}", file=sys.stderr)

    headers = {
        "User-Agent": "Mozilla/5.0 (SpotstatsAi stats updater)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = requests.get(proxied, headers=headers, timeout=45)
    resp.raise_for_status()
    return resp.text


def _get_float(row, stat: str):
    cell = row.find("td", {"data-stat": stat})
    txt = cell.get_text(strip=True) if cell else ""
    if txt in ("", "NA"):
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def _get_int(row, stat: str):
    cell = row.find("td", {"data-stat": stat})
    txt = cell.get_text(strip=True) if cell else ""
    if not txt:
        return None
    try:
        return int(txt)
    except ValueError:
        return None


def parse_per_game():
    """
    Scrape the per-game table (id='per_game_stats') from BR (via proxy).

    Returns:
      per_by_name_team: {(name, team): stats_dict}
      tot_by_name: {name: stats_dict} for rows where Tm == 'TOT'
    """
    html = fetch_html_via_proxy(PER_GAME_URL)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="per_game_stats")
    if table is None:
        raise RuntimeError("Could not find table with id='per_game_stats'")

    tbody = table.find("tbody")
    rows = tbody.find_all("tr")

    per_by_name_team: Dict[Tuple[str, str], dict] = {}
    tot_by_name: Dict[str, dict] = {}

    for row in rows:
        # Skip header sub-rows
        if row.get("class") and "thead" in row["class"]:
            continue

        player_cell = row.find("td", {"data-stat": "player"})
        team_cell = row.find("td", {"data-stat": "team_id"})
        if player_cell is None or team_cell is None:
            continue

        name = player_cell.get_text(strip=True)
        team = team_cell.get_text(strip=True)

        record = {
            "games": _get_int(row, "g") or 0,
            "min": _get_float(row, "mp_per_g") or 0.0,
            "pts": _get_float(row, "pts_per_g") or 0.0,
            "reb": _get_float(row, "trb_per_g") or 0.0,
            "ast": _get_float(row, "ast_per_g") or 0.0,
            "stl": _get_float(row, "stl_per_g") or 0.0,
            "blk": _get_float(row, "blk_per_g") or 0.0,
            "tov": _get_float(row, "tov_per_g") or 0.0,
            "fg3a": _get_float(row, "fg3a_per_g") or 0.0,
            "fg3_pct": _get_float(row, "fg3_pct") or 0.0,
            "fga": _get_float(row, "fga_per_g") or 0.0,
            "fg_pct": _get_float(row, "fg_pct") or 0.0,
            "fta": _get_float(row, "fta_per_g") or 0.0,
            "ft_pct": _get_float(row, "ft_pct") or 0.0,
        }

        if team == "TOT":
            tot_by_name[name] = record
        else:
            per_by_name_team[(name, team)] = record

    return per_by_name_team, tot_by_name


def parse_advanced_usage():
    """
    Scrape the advanced table (id='advanced_stats') and pull USG%.

    Returns:
      usage_by_name: {name: usage_float}
    """
    html = fetch_html_via_proxy(ADV_URL)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="advanced_stats")
    if table is None:
        raise RuntimeError("Could not find table with id='advanced_stats'")

    tbody = table.find("tbody")
    rows = tbody.find_all("tr")

    usage_by_name: Dict[str, float] = {}

    for row in rows:
        if row.get("class") and "thead" in row["class"]:
            continue

        player_cell = row.find("td", {"data-stat": "player"})
        team_cell = row.find("td", {"data-stat": "team_id"})
        if player_cell is None or team_cell is None:
            continue

        name = player_cell.get_text(strip=True)
        team = team_cell.get_text(strip=True)
        usg = _get_float(row, "usg_pct")
        if usg is None:
            continue

        if team == "TOT":
            usage_by_name[name] = usg
        else:
            usage_by_name.setdefault(name, usg)

    return usage_by_name


def main():
    # 1) Load rosters.json so we only keep players you care about
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    # 2) Scrape per-game and advanced usage
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
