#!/usr/bin/env python3
"""
Pull current-season PER GAME + ADVANCED stats from Basketball Reference
(via your Cloudflare Worker proxy) and produce player_stats.json
matching app.js expectations.

This version:
- Supports BR "comment-wrapped" tables (<!-- ... -->)
- Scrapes correctly from bbr-proxy Worker
- Produces perfect stats for players in rosters.json
"""

import json
import sys
import requests
from bs4 import BeautifulSoup, Comment

# ============ CONFIG ============

YEAR = 2026
PROXY = "https://bbr-proxy.dblair1027.workers.dev/?url="

PER_GAME_HTML = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_per_game.html"
ADV_HTML      = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_advanced.html"

PER_GAME_ID = "per_game_stats"
ADVANCED_ID = "advanced"

TEAM_ALIASES = {
    "BKN": "BRK",
    "CHA": "CHO",
    "PHX": "PHO",
}

def to_bref_team(c):
    return TEAM_ALIASES.get(c, c)

# ============ FETCH HELPERS ============

def fetch_via_proxy(url: str) -> str:
    full = PROXY + requests.utils.quote(url, safe="")
    print(f"Fetching via proxy: {full}", file=sys.stderr)

    headers = {
        "User-Agent": "Mozilla/5.0 (SpotstatsAi Scraper)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = requests.get(full, headers=headers, timeout=40)
    resp.raise_for_status()
    return resp.text

# ============ TABLE SCRAPER ============

def extract_commented_tables(soup: BeautifulSoup):
    """Return a list of extracted HTML tables that were inside <!-- --> comments."""
    tables = []
    for c in soup.find_all(string=lambda text: isinstance(text, Comment)):
        try:
            sub = BeautifulSoup(c, "html.parser")
            for t in sub.find_all("table"):
                tables.append(t)
        except Exception:
            continue
    return tables

def get_table(html: str, table_id: str):
    soup = BeautifulSoup(html, "html.parser")

    # 1. Try direct first
    table = soup.find("table", id=table_id)
    if table:
        return table

    # 2. Try inside comment-wrapped tables
    for t in extract_commented_tables(soup):
        if t.get("id") == table_id:
            return t

    raise RuntimeError(f"Table id='{table_id}' not found (even in comments)")

# ============ PARSE PER-GAME ============

def parse_per_game():
    html = fetch_via_proxy(PER_GAME_HTML)
    table = get_table(html, PER_GAME_ID)

    tbody = table.find("tbody")
    rows = tbody.find_all("tr")

    per = {}
    tot = {}

    # NOTE: Basketball-Reference puts the player name in a <th>, not <td>.
    # We look for ANY element with the given data-stat.
    def cell(r, stat):
        el = r.find(attrs={"data-stat": stat})
        return el.get_text(strip=True) if el else ""

    def num(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    for r in rows:
        if "class" in r.attrs and "thead" in r["class"]:
            continue

        name = cell(r, "player")
        team = cell(r, "team_id")

        if not name or not team:
            continue

        rec = {
            "games": int(num(cell(r, "g"))),
            "min":  num(cell(r, "mp_per_g")),
            "pts":  num(cell(r, "pts_per_g")),
            "reb":  num(cell(r, "trb_per_g")),
            "ast":  num(cell(r, "ast_per_g")),
            "stl":  num(cell(r, "stl_per_g")),
            "blk":  num(cell(r, "blk_per_g")),
            "tov":  num(cell(r, "tov_per_g")),
            "fg3a": num(cell(r, "fg3a_per_g")),
            "fg3_pct": num(cell(r, "fg3_pct")),
            "fga":  num(cell(r, "fga_per_g")),
            "fg_pct": num(cell(r, "fg_pct")),
            "fta":  num(cell(r, "fta_per_g")),
            "ft_pct": num(cell(r, "ft_pct")),
        }

        if team == "TOT":
            tot[name] = rec
        else:
            per[(name, team)] = rec

    return per, tot

# ============ PARSE ADVANCED ============

def parse_advanced():
    html = fetch_via_proxy(ADV_HTML)
    table = get_table(html, ADVANCED_ID)

    rows = table.find("tbody").find_all("tr")
    usage = {}

    # Same fix here: look for any element with data-stat
    def cell(r, stat):
        el = r.find(attrs={"data-stat": stat})
        return el.get_text(strip=True) if el else ""

    for r in rows:
        if "class" in r.attrs and "thead" in r["class"]:
            continue

        name = cell(r, "player")
        team = cell(r, "team_id")
        usg  = cell(r, "usg_pct")

        if not name:
            continue

        try:
            val = float(usg)
        except Exception:
            val = 0.0

        # Prefer TOT row first
        if team == "TOT":
            usage[name] = val
        else:
            usage.setdefault(name, val)

    return usage

# ============ MAIN ============

def main():
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    per, tot = parse_per_game()
    usage = parse_advanced()

    final = {}
    missing = []

    for team_code, players in rosters.items():
        bteam = to_bref_team(team_code)

        for name in players:
            stats = per.get((name, bteam))
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
