#!/usr/bin/env python3
"""
Builds player_stats.json using the BallDontLie API (PRO).

- Uses rosters.json to know which players you care about
- Uses schedule.json to attach today's opponent
- Pulls season per-game averages from /season_averages
- Pulls last-5-games rolling averages from /stats
- Produces:
   {
     "Player Name": {
       "team": "TOR",
       "season": 2025,
       "games": ...,
       "min": ...,
       "pts": ...,
       "reb": ...,
       "ast": ...,
       "fg_pct": ...,
       "fg3_pct": ...,
       "ft_pct": ...,
       "last5_pts": ...,
       "last5_reb": ...,
       "last5_ast": ...,
       "opponent": "NYK",
       "def_rank": null,
       ...
     },
     ...
   }

Environment:
 BDL_API_KEY  -> your BallDontLie API key (Bearer token)
 BDL_SEASON   -> optional override, e.g. 2025
"""

import json
import os
import sys
from datetime import date
from time import sleep
from typing import Dict, List, Tuple, Any

import requests

BDL_BASE = "https://api.balldontlie.io/v1"

API_KEY = os.getenv("BDL_API_KEY", "").strip()
if not API_KEY:
   print("ERROR: BDL_API_KEY is not set", file=sys.stderr)
   sys.exit(1)


# ---------------------------------------------------------------------------
# Season handling
# ---------------------------------------------------------------------------

def detect_season() -> int:
   """
   Auto-detect current season start year, with override.

   BallDontLie uses the YEAR THE SEASON STARTS, e.g.
     2023 -> 2023-24 season
     2024 -> 2024-25 season
   """
   override = os.getenv("BDL_SEASON")
   if override:
       try:
           val = int(override)
           print(f"Using BDL_SEASON override: {val}", file=sys.stderr)
           return val
       except ValueError:
           print(f"WARNING: invalid BDL_SEASON={override!r}, ignoring", file=sys.stderr)

   today = date.today()
   # NBA season typically starts Oct
   if today.month >= 10:
       return today.year
   return today.year - 1


SEASON = detect_season()
TODAY = date.today().isoformat()

print(f"Using BallDontLie season: {SEASON}", file=sys.stderr)
print(f"Today: {TODAY}", file=sys.stderr)


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def bdl_get(path: str, params: Any = None) -> dict:
   """
   Low-level GET wrapper with auth + retry.
   'params' can be a dict or list of (key, value) tuples.
   """
   url = f"{BDL_BASE}/{path}"
   headers = {
       "Authorization": f"Bearer {API_KEY}",
       "Accept": "application/json",
   }

   for attempt in range(3):
       try:
           r = requests.get(url, headers=headers, params=params, timeout=30)
           r.raise_for_status()
           return r.json()
       except requests.RequestException as e:
           print(f"[bdl_get] ERROR ({attempt+1}/3): {e} for url: {r.url if 'r' in locals() else url}",
                 file=sys.stderr)
           if attempt == 2:
               raise
           sleep(1.5)

   # Should not reach here
   raise RuntimeError("bdl_get: exhausted retries")


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def norm_name(name: str) -> str:
   """Normalize player names so roster names match BDL names more often."""
   return (
       name.lower()
       .replace(".", "")
       .replace("'", "")
       .replace("-", " ")
       .strip()
   )


def parse_minutes(min_str: str | None) -> float:
   """
   BallDontLie returns minutes as 'MM:SS'.
   Convert to decimal minutes (e.g. '31:24' -> 31.4).
   """
   if not min_str:
       return 0.0
   try:
       mm, ss = min_str.split(":")
       return round(int(mm) + int(ss) / 60.0, 1)
   except Exception:
       return 0.0


# ---------------------------------------------------------------------------
# Players index
# ---------------------------------------------------------------------------

def fetch_players_index() -> Dict[str, Dict]:
   """
   Build mapping:
       normalized_full_name -> {id, team_abbrev, full_name}
   using /players with pagination.
   """
   print("Fetching league player index…", file=sys.stderr)
   players_by_name: Dict[str, Dict] = {}

   page = 1
   per_page = 100

   while True:
       data = bdl_get("players", params={"page": page, "per_page": per_page})
       players = data.get("data", [])
       if not players:
           break

       for p in players:
           full = f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip()
           key = norm_name(full)
           team = (p.get("team") or {}).get("abbreviation")
           players_by_name[key] = {
               "id": p["id"],
               "team": team,
               "full_name": full,
           }

       meta = data.get("meta", {})
       total_pages = meta.get("total_pages", page)
       print(f"  players page {page}/{total_pages}", file=sys.stderr)

       if page >= total_pages:
           break
       page += 1

   print(f"Indexed {len(players_by_name)} players.", file=sys.stderr)
   return players_by_name


# ---------------------------------------------------------------------------
# Season averages + last-5 helpers
# ---------------------------------------------------------------------------

def fetch_season_averages_batch(player_ids: List[int], season: int) -> Dict[int, dict]:
   """
   Call /season_averages in one shot for a small batch of player IDs.

   PRO docs: use 'season' and repeated 'player_ids' (no brackets).
   """
   if not player_ids:
       return {}

   params: List[Tuple[str, Any]] = [("season", season)]
   for pid in player_ids:
       params.append(("player_ids", pid))

   data = bdl_get("season_averages", params=params)
   out: Dict[int, dict] = {}
   for row in data.get("data", []):
       pid = row.get("player_id")
       if pid is not None:
           out[int(pid)] = row
   return out


def fetch_last5_for_player(pid: int, season: int) -> dict | None:
   """
   Fetch last 5 games for a single player via /stats.

   We keep this per-player (not batch) to avoid surprises in the PRO params.
   """
   params = {
       "seasons": season,          # PRO prefers 'seasons' (no []), may repeat but 1 is enough
       "player_ids": pid,
       "per_page": 5,
       "page": 1,
       "postseason": "false",
       "sort": "game.date:desc",
   }
   data = bdl_get("stats", params=params)
   games = data.get("data", [])
   if not games:
       return None

   n = len(games)
   tot_pts = sum(g.get("pts", 0) for g in games)
   tot_reb = sum(g.get("reb", 0) for g in games)
   tot_ast = sum(g.get("ast", 0) for g in games)

   return {
       "pts": round(tot_pts / n, 1),
       "reb": round(tot_reb / n, 1),
       "ast": round(tot_ast / n, 1),
   }


# ---------------------------------------------------------------------------
# Schedule → opponent mapping
# ---------------------------------------------------------------------------

def load_schedule() -> dict:
   with open("schedule.json", "r", encoding="utf-8") as f:
       return json.load(f)


def build_today_opponents(schedule: dict) -> Dict[str, str]:
   """
   From schedule.json, build mapping: team_code -> opponent_code for TODAY.
   """
   games_today = schedule.get(TODAY, []) or []
   mapping: Dict[str, str] = {}
   for g in games_today:
       home = g["home_team"]
       away = g["away_team"]
       mapping[home] = away
       mapping[away] = home
   return mapping


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_player_stats() -> Dict[str, dict]:
   # Load local inputs
   with open("rosters.json", "r", encoding="utf-8") as f:
       rosters = json.load(f)

   schedule = load_schedule()
   opponents = build_today_opponents(schedule)
   players_index = fetch_players_index()

   # Map roster names -> BDL ids
   roster_name_to_id: Dict[str, int] = {}
   missing: list[tuple[str, str]] = []

   for team_code, player_list in rosters.items():
       for name in player_list:
           key = norm_name(name)
           info = players_index.get(key)
           if not info:
               missing.append((name, team_code))
               continue
           roster_name_to_id[name] = info["id"]

   print(f"Total matched players: {len(roster_name_to_id)}", file=sys.stderr)

   # ------------------------------------------------------------------
   # Fetch season averages in SMALL batches to avoid 400s
   # ------------------------------------------------------------------
   all_ids = list(set(roster_name_to_id.values()))
   season_avgs_by_id: Dict[int, dict] = {}
   chunk_size = 10  # small on purpose

   print("Fetching SEASON AVERAGES in batches…", file=sys.stderr)
   for i in range(0, len(all_ids), chunk_size):
       chunk = all_ids[i:i + chunk_size]
       try:
           batch = fetch_season_averages_batch(chunk, SEASON)
       except requests.HTTPError as e:
           print(f"  !! season_averages batch failed for IDs {chunk}: {e}", file=sys.stderr)
           continue
       season_avgs_by_id.update(batch)

   # ------------------------------------------------------------------
   # Build final player_stats map
   # ------------------------------------------------------------------
   final: Dict[str, dict] = {}

   for team_code, player_list in rosters.items():
       for name in player_list:
           pid = roster_name_to_id.get(name)
           avg = season_avgs_by_id.get(pid) if pid is not None else None

           # Season averages
           games = avg.get("games_played", 0) if avg else 0
           min_val = parse_minutes(avg.get("min")) if avg else 0.0
           pts = float(avg.get("pts", 0.0)) if avg else 0.0
           reb = float(avg.get("reb", 0.0)) if avg else 0.0
           ast = float(avg.get("ast", 0.0)) if avg else 0.0

           fg_pct = avg.get("fg_pct") if avg else None
           fg3_pct = avg.get("fg3_pct") if avg else None
           ft_pct = avg.get("ft_pct") if avg else None

           # Last 5-game rolling
           if pid is not None:
               last5 = fetch_last5_for_player(pid, SEASON)
           else:
               last5 = None

           last5_pts = last5["pts"] if last5 else 0.0
           last5_reb = last5["reb"] if last5 else 0.0
           last5_ast = last5["ast"] if last5 else 0.0

           opp_team = opponents.get(team_code)

           final[name] = {
               "team": team_code,

               "season": SEASON,
               "games": games,
               "min": min_val,
               "pts": pts,
               "reb": reb,
               "ast": ast,
               "fg_pct": fg_pct,
               "fg3_pct": fg3_pct,
               "ft_pct": ft_pct,

               "last5_pts": last5_pts,
               "last5_reb": last5_reb,
               "last5_ast": last5_ast,

               "opponent": opp_team,
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

               # Keep placeholders your UI already knows how to read
               "usage": 0.0,
               "pace": None,
           }

   if missing:
       print("\nPlayers not matched between rosters.json and BallDontLie:", file=sys.stderr)
       for name, team in missing:
           print(f"  - {name} ({team})", file=sys.stderr)

   return final


def main() -> None:
   print("Building BallDontLie-based player_stats.json…", file=sys.stderr)
   stats = build_player_stats()

   with open("player_stats.json", "w", encoding="utf-8") as f:
       json.dump(stats, f, indent=2, sort_keys=True)

   print(f"Wrote player_stats.json with {len(stats)} players.", file=sys.stderr)


if __name__ == "__main__":
   main()
