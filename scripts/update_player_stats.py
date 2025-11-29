#!/usr/bin/env python3
"""
Pull current-season PER GAME + ADVANCED stats from Basketball Reference
(via your Cloudflare Worker proxy) and produce player_stats.json
matching app.js expectations.

Fully patched version:
- Handles BR "comment wrapped" tables
- Properly extracts player names from <th>
- Normalizes names ("Adebayo, Bam" -> "Bam Adebayo")
- Resolves TOT vs team rows correctly
- Works behind Cloudflare Worker
- Produces correct JSON for your Prop Engine
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


# ---------- NAME NORMALIZATION ----------
def normalize_name(name: str) -> str:
    """Convert BR names like 'Adebayo, Bam*' to 'Bam Adebayo'."""
    name = name.replace("*", "").replace("†", "").strip()

    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
        return f"{first} {last}"

    return name


# ---------- FETCH HELPERS ----------
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


# ---------- COMMENTED TABLE EXTRACTION ----------
def extract_commented_tables(soup: BeautifulSoup):
    tables = []
    for c in soup.find_all(string=lambda text: isinstance(text, Comment)):
        try:
            sub = BeautifulSoup(c, "html.parser")
            for t in sub.find_all("table"):
                tables.append(t)
        except:
            continue
    return tables


# ---------- LOAD TABLE ----------
def get_table(html: str, table_id: str):
    soup = BeautifulSoup(html, "html.parser")

    # 1. Direct table
    table = soup.find("table", id=table_id)
    if table:
        return table

    # 2. Commented tables
    for t in extract_commented_tables(soup):
        if t.get("id") == table_id:
            return t

    raise RuntimeError(f"Table id='{table_id}' NOT found (even in comments)")


# ---------- PER GAME PARSER ----------
def parse_per_game():
    html = fetch_via_proxy(PER_GAME_HTML)
    table = get_table(html, PER_GAME_ID)

    tbody = table.find("tbody")
    rows = tbody.find_all("tr")

    per = {}
    tot = {}

    def cell(r, stat):
        td = r.find("td", {"data-stat": stat})
        if td:
            return td.get_text(strip=True)

        # Some player names appear in <th>
        th = r.find("th", {"data-stat": stat})
        return th.get_text(strip=True) if th else ""

    def num(v):
        try:
            return float(v)
        except:
            return 0.0

    for r in rows:
        if "class" in r.attrs and "thead" in r["class"]:
            continue

        raw_name = cell(r, "player")
        name = normalize_name(raw_name)
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


# ---------- ADVANCED PARSER ----------
def parse_advanced():
    html = fetch_via_proxy(ADV_HTML)
    table = get_table(html, ADVANCED_ID)

    rows = table.find("tbody").find_all("tr")
    usage = {}

    def cell(r, stat):
        td = r.find("td", {"data-stat": stat})
        if td:
            return td.get_text(strip=True)
        th = r.find("th", {"data-stat": stat})
        return th.get_text(strip=True) if th else ""

    for r in rows:
        if "class" in r.attrs and "thead" in r["class"]:
            continue

        raw_name = cell(r, "player")
        name = normalize_name(raw_name)
        team = cell(r, "team_id")
        usg  = cell(r, "usg_pct")

        if not name:
            continue

        try:
            val = float(usg)
        except:
            val = 0.0

        if team == "TOT":
            usage[name] = val
        else:
            usage.setdefault(name, val)

    return usage


# ---------- MAIN ----------
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
