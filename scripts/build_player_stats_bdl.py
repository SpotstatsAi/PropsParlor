#!/usr/bin/env python3
"""
Build player_stats.json using the BallDontLie API.

- Reads:
   rosters.json   -> team_code -> [player names]
   schedule.json  -> today's games (to attach opponent)

- Fetches from BallDontLie:
   /players         -> league-wide player index (id + team + name)
   /season_averages -> per-player season per-game stats
   /stats           -> last 5 games per player

- Writes:
   player_stats.json -> { "Player Name": { ...stats... }, ... }

Environment variables (GitHub secrets):
   BDL_API_KEY or BALLDONTLIE_API_KEY  -> your BallDontLie API key
   BDL_SEASON (optional)               -> override season start year, e.g. 2025
"""

import json
import os
import sys
from datetime import date
from time import sleep
from typing import Dict, Any, List, Optional

import requests


BDL_BASE = "https://api.balldontlie.io/v1"

# ---------------------------------------------------------------------------
# API key + season detection
# ---------------------------------------------------------------------------

API_KEY = (os.getenv("BDL_API_KEY") or os.getenv("BALLDONTLIE_API_KEY") or "").strip()
if not API_KEY:
   print("ERROR: BDL_API_KEY / BALLDONTLIE_API_KEY is not set", file=sys.stderr)
   sys.exit(1)


def detect_season() -> int:
   """
   Auto-detect NBA season based on today's date.

   BallDontLie seasons are referenced by the YEAR they start.
   Example: 2025-26 season => 2025
   """
   override = os.getenv("BDL_SEASON")
   if override:
       try:
           season_val = int(override)
           print(f"Using overridden BDL season: {season_val}", file=sys.stderr)
           return season_val
       except ValueError:
           print(f"WARNING: invalid BDL_SEASON={override!r}, ignoring", file=sys.stderr)

   today = date.today()
   # If we're in Oct/Nov/Dec, season == current year; otherwise current_year - 1
   if today.month >= 10:
       season_val = today.year
   else:
       season_val = today.year - 1

   print(f"Auto-detected BDL season: {season_val}", file=sys.stderr)
   return season_val


SEASON = detect_season()
TODAY = date.today().isoformat()

print(f"Using BDL Season: {SEASON}", file=sys.stderr)
print(f"Today: {TODAY}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def bdl_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
   """
   Low-level GET wrapper with Authorization header + basic retry.

   Special handling:
     - If response is 400, we log it and return {} instead of crashing the build.
       This lets us treat that player as "no data" and continue.
   """
   url = f"{BDL_BASE}/{path}"
   headers = {
       "Authorization": f"Bearer {API_KEY}",
       "Accept": "application/json",
   }

   for attempt in range(3):
       try:
           resp = requests.get(url, headers=headers, params=params, timeout=30)

           if resp.status_code == 400:
               # Bad request (often a player with no data for that season) – log & skip
               try:
                   err_payload = resp.json()
               except Exception:
                   err_payload = resp.text
               print(
                   f"[bdl_get] 400 for {url} params={params} attempt {attempt+1}: {err_payload}",
                   file=sys.stderr,
               )
               return {}

           resp.raise_for_status()
           return resp.json()

       except requests.RequestException as e:
           print(
               f"[bdl_get] ERROR: {e} on {url} params={params} attempt {attempt+1}/3",
               file=sys.stderr,
           )
           if attempt == 2:
               raise
           sleep(1.5)

   raise RuntimeError("bdl_get: exhausted retries")


def norm_name(name: str) -> str:
   """Normalize player names so rosters & BDL match more reliably."""
   return (
       name.lower()
       .replace(".", "")
       .replace("'", "")
       .replace("-", " ")
       .strip()
   )


def parse_minutes(min_val: Any) -> float:
   """
   Convert a minutes value to a float:

     - If it's like "31:24" -> 31.4 (approx)
     - If it's already numeric -> float
   """
   if min_val is None:
       return 0.0

   # String "MM:SS"
   if isinstance(min_val, str):
       try:
           parts = min_val.split(":")
           if len(parts) != 2:
               return 0.0
           mins = int(parts[0])
           secs = int(parts[1])
           return round(mins + secs / 60.0, 1)
       except Exception:
           return 0.0

   # Numeric
   try:
       return float(min_val)
   except Exception:
       return 0.0


# ---------------------------------------------------------------------------
# League player index
# ---------------------------------------------------------------------------

def fetch_players_index() -> Dict[str, Dict[str, Any]]:
   """
   Build a mapping:
       normalized_full_name -> {id, team_abbrev, full_name}

   Uses /players with pagination across ALL pages.
   """
   print("Fetching BallDontLie player index…", file=sys.stderr)

   players_by_name: Dict[str, Dict[str, Any]] = {}

   page = 1
   per_page = 100

   while True:
       data = bdl_get("players", params={"page": page, "per_page": per_page})
       players = data.get("data") or []
       if not players:
           break

       for p in players:
           first = (p.get("first_name") or "").strip()
           last = (p.get("last_name") or "").strip()
           full = f"{first} {last}".strip()
           key = norm_name(full)
           team = (p.get("team") or {}).get("abbreviation")

           players_by_name[key] = {
               "id": p.get("id"),
               "team": team,
               "full_name": full,
           }

       meta = data.get("meta") or {}
       total_pages = meta.get("total_pages") or page
       print(
           f"  players page {page}/{total_pages} (batch size {len(players)})",
           file=sys.stderr,
       )

       if page >= total_pages:
           break
       page += 1

   print(f"Indexed {len(players_by_name)} players.", file=sys.stderr)
   return players_by_name


# ---------------------------------------------------------------------------
# BallDontLie data fetches
# ---------------------------------------------------------------------------

def fetch_season_avg(player_id: int, season: int) -> Optional[Dict[str, Any]]:
   """
   Fetch per-game season averages for one player.

   Endpoint (premium):
     /season_averages?season=YYYY&player_id=ID

   Returns the single data row dict, or None if no data.
   """
   params = {
       "season": season,
       "player_id": player_id,
   }
   data = bdl_get("season_averages", params=params)
   arr = data.get("data") if isinstance(data, dict) else None
   if not arr:
       return None
   return arr[0]


def fetch_last5(player_id: int, season: int) -> Optional[Dict[str, float]]:
   """
   Compute rolling averages over the last 5 games.

   Endpoint:
     /stats?seasons[]=YYYY&player_ids[]=ID&per_page=5&page=1&postseason=false&sort=game.date:desc
   """
   params = {
       "seasons[]": season,
       "player_ids[]": player_id,
       "per_page": 5,
       "page": 1,
       "postseason": "false",
       "sort": "game.date:desc",
   }
   data = bdl_get("stats", params=params)
   games = data.get("data") if isinstance(data, dict) else None
   if not games:
       return None

   n = len(games)
   tot_pts = sum(g.get("pts", 0.0) for g in games)
   tot_reb = sum(g.get("reb", 0.0) for g in games)
   tot_ast = sum(g.get("ast", 0.0) for g in games)

   return {
       "pts": round(tot_pts / n, 1),
       "reb": round(tot_reb / n, 1),
       "ast": round(tot_ast / n, 1),
   }


# ---------------------------------------------------------------------------
# Schedule / opponent helpers
# ---------------------------------------------------------------------------

def load_schedule() -> Dict[str, Any]:
   with open("schedule.json", "r", encoding="utf-8") as f:
       return json.load(f)


def today_opponents(schedule: Dict[str, Any]) -> Dict[str, str]:
   """
   Build mapping team_code -> opponent_code for today's date based on schedule.json.
   """
   games_today = schedule.get(TODAY) or []
   opp: Dict[str, str] = {}
   for g in games_today:
       home = g["home_team"]
       away = g["away_team"]
       opp[home] = away
       opp[away] = home
   return opp


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_player_stats() -> Dict[str, Dict[str, Any]]:
   # Load rosters & schedule
   with open("rosters.json", "r", encoding="utf-8") as f:
       rosters: Dict[str, List[str]] = json.load(f)

   schedule = load_schedule()
   opp_map = today_opponents(schedule)

   # League player index from BallDontLie
   players_index = fetch_players_index()

   # Caches so we only hit the API once per player
   avg_cache: Dict[int, Optional[Dict[str, Any]]] = {}
   last5_cache: Dict[int, Optional[Dict[str, float]]] = {}

   final: Dict[str, Dict[str, Any]] = {}
   unmatched: List[str] = []

   # Very light throttle: BDL trial QPS is low; sleep a bit between API calls
   THROTTLE_SECONDS = 0.25

   for team_code, player_names in rosters.items():
       print(f"Processing roster for {team_code} ({len(player_names)} players)…", file=sys.stderr)

       for name in player_names:
           key = norm_name(name)
           pinfo = players_index.get(key)

           if not pinfo or pinfo.get("id") is None:
               unmatched.append(f"{name} ({team_code})")
               player_id = None
               avg = None
               last5 = None
           else:
               player_id = int(pinfo["id"])

               # Season averages
               if player_id not in avg_cache:
                   sleep(THROTTLE_SECONDS)
                   avg_cache[player_id] = fetch_season_avg(player_id, SEASON)
               avg = avg_cache[player_id]

               # Last 5-game rolling averages
               if player_id not in last5_cache:
                   sleep(THROTTLE_SECONDS)
                   last5_cache[player_id] = fetch_last5(player_id, SEASON)
               last5 = last5_cache[player_id]

           # Extract season numbers with safe defaults
           games_played = avg.get("games_played", 0) if avg else 0
           min_val = parse_minutes(avg.get("min") if avg else None)
           pts = float(avg.get("pts", 0.0)) if avg else 0.0
           reb = float(avg.get("reb", 0.0)) if avg else 0.0
           ast = float(avg.get("ast", 0.0)) if avg else 0.0

           fg_pct = avg.get("fg_pct") if avg else None
           fg3_pct = avg.get("fg3_pct") if avg else None
           ft_pct = avg.get("ft_pct") if avg else None

           # Last 5
           last5_pts = last5["pts"] if last5 else 0.0
           last5_reb = last5["reb"] if last5 else 0.0
           last5_ast = last5["ast"] if last5 else 0.0

           opponent_team = opp_map.get(team_code)

           final[name] = {
               "team": team_code,
               "season": SEASON,

               # Season averages (per game)
               "games": games_played,
               "min": min_val,
               "pts": pts,
               "reb": reb,
               "ast": ast,
               "fg_pct": fg_pct,
               "fg3_pct": fg3_pct,
               "ft_pct": ft_pct,

               # Last 5-game rolling averages
               "last5_pts": last5_pts,
               "last5_reb": last5_reb,
               "last5_ast": last5_ast,

               # Matchup info (from schedule.json)
               "opponent": opponent_team,
               "def_rank": None,
               "team_record": None,
               "team_win_pct": None,
               "opp_record": None,
               "opp_win_pct": None,
               "opp_streak": None,
               "opp_points_for": None,
               "opp_points_against": None,
               "opp_conf_rank": None,
               "opp_div_rank": None,

               # Fields your UI expects but BDL doesn't provide
               "usage": 0.0,
               "pace": None,
           }

   if unmatched:
       print("\n[WARN] Players in rosters.json not matched to BallDontLie:", file=sys.stderr)
       for line in unmatched:
           print(f"  - {line}", file=sys.stderr)

   return final


def main() -> None:
   print("Building player_stats.json from BallDontLie…", file=sys.stderr)
   stats = build_player_stats()

   with open("player_stats.json", "w", encoding="utf-8") as f:
       json.dump(stats, f, indent=2, sort_keys=True)

   print(f"Wrote player_stats.json with {len(stats)} players.", file=sys.stderr)


if __name__ == "__main__":
   main()
