#!/usr/bin/env python3
"""
Pull current-season PER GAME + ADVANCED stats from Basketball Reference
(via your Cloudflare Worker proxy) and produce player_stats.json
matching app.js expectations.

- Uses real BR table IDs:
    per-game:  id="per_game_stats"
    advanced:  id="advanced"
- Handles comment-wrapped tables (<!-- ... -->) just in case.
- Maps BKN->BRK, CHA->CHO, PHX->PHO for Basketball-Reference.
"""

import json
import sys
import requests
from bs4 import BeautifulSoup, Comment

# ============ CONFIG ============

# Set this to the season you want (e.g. 2025 or 2026)
YEAR = 2026

# Your Cloudflare Worker proxy
PROXY = "https://bbr-proxy.dblair1027.workers.dev/?url="

PER_GAME_HTML = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_per_game.html"
ADV_HTML      = f"https://www.basketball-reference.com/leagues/NBA_{YEAR}_advanced.html"

# **These IDs are what BR actually uses**
PER_GAME_ID = "per_game_stats"
ADVANCED_ID = "advanced"

# Team code mapping: our JSON -> Basketball-Reference
TEAM_ALIASES = {
    "BKN": "BRK",
    "CHA": "CHO",
    "PHX": "PHO",
}

def to_bref_team(code: str) -> str:
    return TEAM_ALIASES.get(code, code)


# ============ FETCH HELPERS ============

def fetch_via_proxy(url: str) -> str:
    """
    Fetch a Basketball-Reference page through the Cloudflare Worker.
    """
    full = PROXY + requests.utils.quote(url, safe="")
    print(f"[fetch] {full}", file=sys.stderr)

    headers = {
        "User-Agent": "Mozilla/5.0 (SpotstatsAi Scraper)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = requests.get(full, headers=headers, timeout=40)
    resp.raise_for_status()
    return resp.text


# ============ TABLE SCRAPER ============

def extract_commented_tables(soup: BeautifulSoup):
    """
    Some BR tables live inside <!-- ... --> comments.
    This extracts all <table> elements found in those comments.
    """
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
    """
    Return a BeautifulSoup <table> with the given id.
    Try direct lookup first, then search comment-wrapped tables.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) direct
    table = soup.find("table", id=table_id)
    if table:
        return table

    # 2) inside comments
    for t in extract_commented_tables(soup):
        if t.get("id") == table_id:
            return t

    raise RuntimeError(f"Table id='{table_id}' not found (even in comments)")


# ============ PARSE PER-GAME ============

def parse_per_game():
    """
    Parse per-game stats from Basketball-Reference.
    Returns:
      per: dict[(name, team)] -> stats
      tot: dict[name]         -> stats (TOT row only)
    """
    html = fetch_via_proxy(PER_GAME_HTML)
    table = get_table(html, PER_GAME_ID)

    tbody = table.find("tbody")
    rows = tbody.find_all("tr")

    per = {}
    tot = {}

    def cell(r, stat):
        td = r.find("td", {"data-stat": stat})
        return td.get_text(strip=True) if td else ""

    def num(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    for r in rows:
        # Skip header rows inside tbody
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
            # one combined line per player
            tot[name] = rec
        else:
            per[(name, team)] = rec

    return per, tot


# ============ PARSE ADVANCED ============

def parse_advanced():
    """
    Parse advanced stats to get usage% from Basketball-Reference.

    Returns:
      usage: dict[name] -> usg_pct
    """
    html = fetch_via_proxy(ADV_HTML)
    table = get_table(html, ADVANCED_ID)

    rows = table.find("tbody").find_all("tr")
    usage = {}

    def cell(r, stat):
        td = r.find("td", {"data-stat": stat})
        return td.get_text(strip=True) if td else ""

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

        # Prefer TOT row when available
        if team == "TOT":
            usage[name] = val
        else:
            usage.setdefault(name, val)

    return usage


# ============ MAIN ============

def main():
    # 1) Load your rosters.json
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    # 2) Scrape stats
    per, tot = parse_per_game()
    usage = parse_advanced()

    final = {}
    missing = []

    for team_code, players in rosters.items():
        bref_team = to_bref_team(team_code)

        for name in players:
            # Try team-specific line first
            stats = per.get((name, bref_team))
            # Fallback to TOT line (multi-team players)
            if stats is None:
                stats = tot.get(name)

            if stats is None:
                # Not found in BR tables; fill with zeros
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
                # Filled later if you want team-level context
                "pace": None,
                "foul_difficulty": None,
                "blowout_risk": None,
            })

            final[name] = out

    # 3) Write player_stats.json for the UI
    with open("player_stats.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, sort_keys=True)

    # 4) Log any players we didn't find
    if missing:
        print("\n[warning] Players not found in BR stats:", file=sys.stderr)
        for n, t in missing:
            print(f" - {n} ({t})", file=sys.stderr)
    else:
        print("[ok] All roster players matched in BR tables", file=sys.stderr)


if __name__ == "__main__":
    main()
