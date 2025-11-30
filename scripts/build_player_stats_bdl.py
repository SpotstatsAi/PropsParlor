#!/usr/bin/env python3
"""
Builds player_stats.json from balldontlie:

- Uses your existing rosters.json (team → [player names])
- Fetches all players from balldontlie
- Fuzzy matches roster names to balldontlie players
- Pulls season averages for matched players
- Adds today's opponent (for your UI)

Requires:
- requests in requirements.txt
- (optional) env BALDONTLIE_API_KEY for premium (Authorization header)

Output:
- player_stats.json at repo root
"""

import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, Any, List

import requests

# -----------------------
# CONFIG
# -----------------------

# balldontlie base URL (v1)
BALL_URL = "https://api.balldontlie.io/v1"

API_KEY = os.getenv("BALDONTLIE_API_KEY", "").strip()

# NBA seasons are integers in balldontlie (e.g. 2025 for 2025-26)
SEASON = 2025

TODAY = datetime.utcnow().strftime("%Y-%m-%d")


# -----------------------
# HTTP HELPERS
# -----------------------

def bd_get(path: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
   """GET helper for balldontlie with optional auth header."""
   headers = {}
   if API_KEY:
       headers["Authorization"] = API_KEY

   url = BALL_URL + path
   resp = requests.get(url, headers=headers, params=params or {}, timeout=25)
   resp.raise_for_status()
   return resp.json()


# -----------------------
# DATA FETCH
# -----------------------

def fetch_all_players() -> List[Dict[str, Any]]:
   """Fetch all players (all pages) from balldontlie."""
   players: List[Dict[str, Any]] = []
   page = 1
   while True:
       data = bd_get("/players", {"per_page": 100, "page": page})
       players.extend(data["data"])
       meta = data.get("meta", {})
       total_pages = meta.get("total_pages", page)
       if page >= total_pages:
           break
       page += 1
   return players


def fetch_season_averages(player_ids: List[int]) -> Dict[int, Dict[str, Any]]:
   """Fetch season averages for a list of player IDs and return pid → stats."""
   result: Dict[int, Dict[str, Any]] = {}
   if not player_ids:
       return result

   # balldontlie accepts multiple player_ids[] in one call; chunk for safety
   chunk_size = 50
   for i in range(0, len(player_ids), chunk_size):
       chunk = player_ids[i:i + chunk_size]
       params: Dict[str, Any] = {
           "season": SEASON,
           "player_ids[]": chunk,
       }
       data = bd_get("/season_averages", params)
       for row in data.get("data", []):
           pid = row["player_id"]
           result[pid] = row

   return result


def fetch_todays_games() -> List[Dict[str, Any]]:
   """Get today's games so we can attach opponents."""
   data = bd_get("/games", {"dates[]": TODAY, "per_page": 100})
   return data.get("data", [])


# -----------------------
# NAME MATCHING
# -----------------------

def normalize_name(name: str) -> str:
   """Lowercase, strip spaces/punctuation – 'A.J. Lawson' → 'ajlawson'."""
   n = name.lower()
   # keep letters only
   n = re.sub(r"[^a-z]", "", n)
   return n


def build_player_lookup(players: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
   """
   Build a lookup: (norm_name, team_abbr) → player_obj
   using balldontlie players list.
   """
   lookup: Dict[str, Dict[str, Any]] = {}

   for p in players:
       first = p.get("first_name", "") or ""
       last = p.get("last_name", "") or ""
       full = f"{first} {last}".strip()
       team = (p.get("team") or {}).get("abbreviation") or ""

       key = f"{normalize_name(full)}|{team.upper()}"
       lookup[key] = p

   return lookup


# -----------------------
# MAIN
# -----------------------

def main() -> None:
   print("Building player_stats.json from balldontlie…", file=sys.stderr)
   print(f"Season: {SEASON}, Today: {TODAY}", file=sys.stderr)

   # 1) Load your rosters.json
   with open("rosters.json", "r", encoding="utf-8") as f:
       rosters = json.load(f)

   # 2) Pull all players from balldontlie
   print("Fetching players from balldontlie…", file=sys.stderr)
   all_players = fetch_all_players()
   print(f"Total players from API: {len(all_players)}", file=sys.stderr)

   lookup = build_player_lookup(all_players)

   # For fuzzy fallback: norm_name → list of players (any team)
   name_bucket: Dict[str, List[Dict[str, Any]]] = {}
   for p in all_players:
       first = p.get("first_name", "")
       last = p.get("last_name", "")
       full = f"{first} {last}".strip()
       nn = normalize_name(full)
       name_bucket.setdefault(nn, []).append(p)

   # 3) Map roster names → balldontlie player IDs
   name_to_pid: Dict[str, int] = {}
   missing: List[str] = []

   for team_code, players in rosters.items():
       t_abbr = team_code.upper()
       for name in players:
           nn = normalize_name(name)
           key = f"{nn}|{t_abbr}"

           p = lookup.get(key)

           if not p:
               # fallback: ignore team, match on name only
               candidates = name_bucket.get(nn, [])
               if len(candidates) == 1:
                   p = candidates[0]
               elif len(candidates) > 1:
                   # if multiple, try one whose team abbr matches closest
                   for cand in candidates:
                       cand_team = (cand.get("team") or {}).get("abbreviation")
                       if cand_team and cand_team.upper() == t_abbr:
                           p = cand
                           break
                   if not p:
                       # still ambiguous; skip
                       p = None

           if not p:
               missing.append(f"{name} ({t_abbr})")
               continue

           pid = p["id"]
           name_to_pid[name] = pid

   print(f"Matched players: {len(name_to_pid)}", file=sys.stderr)
   if missing:
       print("Unmatched roster entries (will be zeros):", file=sys.stderr)
       for m in missing:
           print(" -", m, file=sys.stderr)

   # 4) Fetch season averages for all matched player IDs
   unique_ids = sorted(set(name_to_pid.values()))
   print(f"Fetching season averages for {len(unique_ids)} players…",
         file=sys.stderr)
   averages_by_pid = fetch_season_averages(unique_ids)

   # 5) Get today's games → opponent by team
   print("Fetching today's games for opponent mapping…", file=sys.stderr)
   todays_games = fetch_todays_games()
   opponent_by_team: Dict[str, str] = {}
   for g in todays_games:
       home = (g.get("home_team") or {}).get("abbreviation")
       away = (g.get("visitor_team") or {}).get("abbreviation")
       if not home or not away:
           continue
       home = home.upper()
       away = away.upper()
       opponent_by_team[home] = away
       opponent_by_team[away] = home

   # 6) Build final player_stats.json structure
   final: Dict[str, Dict[str, Any]] = {}

   def parse_minutes(min_str: str) -> float:
       if not min_str:
           return 0.0
       try:
           parts = min_str.split(":")
           mins = int(parts[0])
           secs = int(parts[1]) if len(parts) > 1 else 0
           return mins + secs / 60.0
       except Exception:
           return 0.0

   for team_code, players in rosters.items():
       t_abbr = team_code.upper()
       opp = opponent_by_team.get(t_abbr)

       for name in players:
           pid = name_to_pid.get(name)
           row = averages_by_pid.get(pid, {}) if pid is not None else {}

           games = row.get("games_played", 0) or 0
           pts = float(row.get("pts", 0.0) or 0.0)
           reb = float(row.get("reb", 0.0) or 0.0)
           ast = float(row.get("ast", 0.0) or 0.0)
           stl = float(row.get("stl", 0.0) or 0.0)
           blk = float(row.get("blk", 0.0) or 0.0)
           tov = float(row.get("turnover", 0.0) or 0.0)
           fg3a = float(row.get("fg3a", 0.0) or 0.0)
           fg3_pct = float(row.get("fg3_pct", 0.0) or 0.0)
           fga = float(row.get("fga", 0.0) or 0.0)
           fg_pct = float(row.get("fg_pct", 0.0) or 0.0)
           fta = float(row.get("fta", 0.0) or 0.0)
           ft_pct = float(row.get("ft_pct", 0.0) or 0.0)
           min_str = row.get("min", "")

           final[name] = {
               "team": t_abbr,
               "season": SEASON,
               "games": games,
               "min": parse_minutes(min_str),
               "pts": pts,
               "reb": reb,
               "ast": ast,
               "stl": stl,
               "blk": blk,
               "tov": tov,
               "fg3a": fg3a,
               "fg3_pct": fg3_pct,
               "fga": fga,
               "fg_pct": fg_pct,
               "fta": fta,
               "ft_pct": ft_pct,

               # for now we don't compute defense ranks/records from balldontlie
               "def_rank": None,
               "opp_conf_rank": None,
               "opp_div_rank": None,
               "opp_points_against": None,
               "opp_points_for": None,
               "opp_record": None,
               "opp_streak": None,
               "opp_win_pct": None,
               "team_record": None,
               "team_win_pct": None,

               # opponent info for today's game
               "opponent": opp,
           }

   # 7) Write out JSON
   with open("player_stats.json", "w", encoding="utf-8") as f:
       json.dump(final, f, indent=2, sort_keys=True)

   print("Wrote player_stats.json", file=sys.stderr)


if __name__ == "__main__":
   main()
