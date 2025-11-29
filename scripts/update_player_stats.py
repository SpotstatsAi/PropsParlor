#!/usr/bin/env python3
"""
Pull current-season PER GAME + ADVANCED stats from Basketball Reference
(via your Cloudflare Worker proxy) and produce player_stats.json
matching app.js expectations.

Table IDs confirmed from your uploaded HTML:
- Per Game table id     = "per_game"
- Advanced stats id     = "advanced"

This script ONLY keeps players that exist in rosters.json.
"""

import json
import sys
import requests
from bs4 import BeautifulSoup
from typing import Dict, Tuple

# ============ CONFIG ============

YEAR = 2026   # 2025–26 season = 2026 on BR

# Your Worker proxy endpoint — DO NOT CHANGE
PROXY = "https://bbr-proxy.dblair1027.workers.dev/?url="

# Source URLs (actual BR)
PER_GAME_HTML = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_per_game.html"
ADV_HTML      = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_advanced.html"

PER_GAME_TABLE_ID = "per_game"
ADV_TABLE_ID      = "advanced"

# alias corrections for discrepancies BR uses
TEAM_ALIASES = {
    "BKN": "BRK",
    "CHA": "CHO",
    "PHX": "PHO",
}

def to_bref_team(code: str) -> str:
    return TEAM_ALIASES.get(code, code)

# ============ HELPERS ============

def fetch_via_proxy(url: str) -> str:
    """Download a webpage through your Cloudflare proxy."""
    full = PROXY + requests.utils.quote(url, safe="")
    print(f"Fetching via proxy: {full}", file=sys.stderr)

    headers = {
        "User-Agent": "Mozilla/5.0 (Spotstats Scraper)",
        "Accept-Language": "en-US,en;q=0.9",
    }

    resp = requests.get(full, headers=headers, timeout=40)
    resp.raise_for_status()

    return resp.text


def scrape_table(url: str, table_id: str):
    """Fetch + parse a single BR HTML table by ID."""
    html = fetch_via_proxy(url)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id=table_id)

    if table is None:
        raise RuntimeError(f"Table id='{table_id}' NOT found at {url}")

    tbody = table.find("tbody")
    return tbody.find_all("tr")


def parse_per_game():
    rows = scrape_table(PER_GAME_HTML, PER_GAME_TABLE_ID)

    per = {}
    tot = {}

    def get(stat):
        return lambda row: (
            row.find("td", {"data-stat": stat}).get_text(strip=True)
            if row.find("td", {"data-stat": stat}) else ""
        )

    get_name = get("player")
    get_team = get("team_id")

    def num(val):
        try:
            return float(val)
        except:
            return 0.0

    for r in rows:
        if "class" in r.attrs and "thead" in r["class"]:
            continue

        name = get_name(r)
        team = get_team(r)

        if not name or not team:
            continue

        rec = {
            "games": int(num(get("g")(r))),
            "min":  num(get("mp_per_g")(r)),
            "pts":  num(get("pts_per_g")(r)),
            "reb":  num(get("trb_per_g")(r)),
            "ast":  num(get("ast_per_g")(r)),
            "stl":  num(get("stl_per_g")(r)),
            "blk":  num(get("blk_per_g")(r)),
            "tov":  num(get("tov_per_g")(r)),
            "fg3a": num(get("fg3a_per_g")(r)),
            "fg3_pct": num(get("fg3_pct")(r)),
            "fga":  num(get("fga_per_g")(r)),
            "fg_pct": num(get("fg_pct")(r)),
            "fta":  num(get("fta_per_g")(r)),
            "ft_pct": num(get("ft_pct")(r)),
        }

        if team == "TOT":
            tot[name] = rec
        else:
            per[(name, team)] = rec

    return per, tot


def parse_advanced():
    rows = scrape_table(ADV_HTML, ADV_TABLE_ID)

    get_usg = lambda r: (
        r.find("td", {"data-stat": "usg_pct"}).get_text(strip=True)
        if r.find("td", {"data-stat": "usg_pct"}) else ""
    )
    get_name = lambda r: (
        r.find("td", {"data-stat": "player"}).get_text(strip=True)
        if r.find("td", {"data-stat": "player"}) else ""
    )
    get_team = lambda r: (
        r.find("td", {"data-stat": "team_id"}).get_text(strip=True)
        if r.find("td", {"data-stat": "team_id"}) else ""
    )

    usage = {}

    for r in rows:
        if "class" in r.attrs and "thead" in r["class"]:
            continue

        name = get_name(r)
        team = get_team(r)
        usg = get_usg(r)

        if not name or not usg:
            continue

        try:
            usg_val = float(usg)
        except:
            usg_val = 0.0

        if team == "TOT":
            usage[name] = usg_val
        else:
            # if no TOT row, use this
            usage.setdefault(name, usg_val)

    return usage


# ============ MAIN ============

def main():
    # Load your rosters first (so we only build stats for real players in your app)
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    per, tot = parse_per_game()
    usage = parse_advanced()

    final = {}
    missing = []

    # Build the stats by matching roster names
    for team_code, players in rosters.items():
        bref_team = to_bref_team(team_code)

        for name in players:

            stats = per.get((name, bref_team))
            if stats is None:
                stats = tot.get(name)

            if stats is None:
                missing.append((name, team_code))
                stats = {
                    "games": 0, "min": 0.0, "pts": 0.0, "reb": 0.0,
                    "ast": 0.0, "stl": 0.0, "blk": 0.0, "tov": 0.0,
                    "fg3a": 0.0, "fg3_pct": 0.0, "fga": 0.0,
                    "fg_pct": 0.0, "fta": 0.0, "ft_pct": 0.0,
                }

            out = dict(stats)
            out.update({
                "team": team_code,
                "season": YEAR,
                "usage": usage.get(name, 0.0),
                # add-ons later if needed
                "pace": None,
                "foul_difficulty": None,
                "blowout_risk": None,
            })

            final[name] = out

    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, sort_keys=True)

    if missing:
        print("\nPlayers not found:", file=sys.stderr)
        for n, t in missing:
            print(f" - {n} ({t})", file=sys.stderr)


if __name__ == "__main__":
    main()
