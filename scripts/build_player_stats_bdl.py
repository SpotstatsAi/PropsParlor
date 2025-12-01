#!/usr/bin/env python3
"""
Builds player_stats.json using the BallDontLie API.

- Uses rosters.json to know which players we care about
- Uses schedule.json to attach today's opponent
- Pulls season per-game averages from /season_averages
- Pulls last-5-games averages from /stats
- Outputs one flat dict: { "Player Name": { ...stats... }, ... }

Environment:
 BDL_API_KEY   -> your BallDontLie API key (Bearer token)
 BDL_SEASON    -> optional override for season (e.g. 2025)

This is designed to work with your existing UI / app.js.
"""

import json
import os
import sys
from datetime import date
from time import sleep

import requests

BDL_BASE = "https://api.balldontlie.io/v1"

API_KEY = os.getenv("BDL_API_KEY", "").strip()
if not API_KEY:
   print("ERROR: BDL_API_KEY is not set", file=sys.stderr)
   sys.exit(1)


def detect_season() -> int:
   """
   Auto-detect NBA season based on today's date.

   BallDontLie seasons are referenced by the YEAR they start.
   Example: 2025-26 season => 2025.
   """
   override = os.getenv("BDL_SEASON")
   if override:
       try:
           season = int(override)
           print(f"Using override BDL_SEASON={season}", file=sys.stderr)
           return season
       except ValueError:
           print(f"WARNING: invalid BDL_SEASON={override!r}, ignoring", file=sys.stderr)

   today = date.today()
   if today.month >= 10:
       return today.year
   return today.year - 1


SEASON = detect_season()
TODAY = date.today().isoformat()

print(f"Using BallDontLie season: {SEASON}", file=sys.stderr)
print(f"Today: {TODAY}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def bdl_get(path: str, params: dict | None = None) -> dict:
   """
   Low-level GET wrapper with auth + simple retry + 429 handling.
   """
   url = f"{BDL_BASE}/{path}"
   headers = {
       "Authorization": f"Bearer {API_KEY}",
       "Accept": "application/json",
   }

   for attempt in range(3):
       try:
           resp = requests.get(url, headers=headers, params=params, timeout=30)
           if resp.status_code == 429:
               # rate limited – back off and retry
               retry_after = int(resp.headers.get("Retry-After", "2"))
               print(f"[bdl_get] 429 rate limit. Sleeping {retry_after}s…", file=sys.stderr)
               sleep(retry_after)
               continue

           resp.raise_for_status()
           return resp.json()
       except requests.RequestException as e:
           print(f"[bdl_get] ERROR ({attempt+1}/3) on {url}: {e}", file=sys.stderr)
           if attempt == 2:
               raise
           sleep(1.5)

   raise RuntimeError("bdl_get: exhausted retries")


def norm_name(name: str) -> str:
   """
   Normalize player names so rosters & BDL match better.
   """
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
       parts = min_str.split(":")
       if len(parts) != 2:
           return 0.0
       mins = int(parts[0])
       secs = int(parts[1])
       return round(mins + secs / 60.0, 1)
   except Exception:
       return 0.0


# ---------------------------------------------------------------------------
# Players index
# ---------------------------------------------------------------------------

def fetch_players_index() -> dict:
   """
   Build mapping from normalized name -> {id, team_abbrev, full_name}.
   Uses /players with pagination.
   """
   print("Fetching league player index…", file=sys.stderr)
   players_by_name: dict[str, dict] = {}

   page = 1
   per_page = 100

   while True:
       data = bdl_get("players", params={"page": page, "per_page": per_page})
       arr = data.get("data", [])
       if not arr:
           break

       for p in arr:
           full = f"{p.get('first_name', '').strip()} {p.get('last_name', '').strip()}".strip()
           key = norm_name(full)
           team = (p.get("team") or {}).get("abbreviation")
           players_by_name[key] = {
               "id": p["id"],
               "team": team,
               "full_name": full,
           }

       meta = data.get("meta", {})
       total_pages = meta.get("total_pages") or page
       print(f"  players page {page}/{total_pages}", file=sys.stderr)

       if page >= total_pages:
           break
       page += 1

   print(f"Indexed {len(players_by_name)} players.", file=sys.stderr)
   return players_by_name


# ---------------------------------------------------------------------------
# Season averages & last-5
# ---------------------------------------------------------------------------

def fetch_season_average(player_id: int, season: int) -> dict | None:
   """
   Fetch per-game season averages for one player.

   Endpoint form (working from your curl test):
     /season_averages?season=2025&player_id=237
   """
   params = {
       "season": season,
       "player_id": player_id,
   }
   data = bdl_get("season_averages", params=params)
   arr = data.get("data", [])
   if not arr:
       return None
   return arr[0]


def fetch_last5(player_id: int) -> dict | None:
   """
   Fetch averages over the last 5 regular-season games.

   We keep this simple to avoid extra 400s:
     /stats?player_id=237&per_page=5&postseason=false&sort=game.date:desc
   """
   params = {
       "player_id": player_id,
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
       "games": n,
   }


# ---------------------------------------------------------------------------
# Schedule → opponents
# ---------------------------------------------------------------------------

def load_schedule() -> dict:
   with open("schedule.json", "r", encoding="utf-8") as f:
       return json.load(f)


def today_opponent_map(schedule: dict) -> dict:
   """
   Build mapping team_code -> opponent_code for today's games.
   """
   games_today = schedule.get(TODAY, []) or []
   opp: dict[str, str] = {}
   for g in games_today:
       home = g["home_team"]
       away = g["away_team"]
       opp[home] = away
       opp[away] = home
   return opp


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_player_stats() -> dict:
   # Load rosters + schedule
   with open("rosters.json", "r", encoding="utf-8") as f:
       rosters = json.load(f)

   schedule = load_schedule()
   opponents = today_opponent_map(schedule)
   players_index = fetch_players_index()

   final: dict[str, dict] = {}
   missing: list[tuple[str, str]] = []

   for team_code, names in rosters.items():
       for name in names:
           key = norm_name(name)
           pinfo = players_index.get(key)

           player_id = None
           season_avg = None
           last5 = None

           if not pinfo:
               # We'll still create an entry, just with zeros.
               missing.append((name, team_code))
           else:
               player_id = pinfo["id"]

               # Per-player calls (no more 400s from giant arrays)
               try:
                   season_avg = fetch_season_average(player_id, SEASON)
               except Exception as e:
                   print(f"[WARN] season_averages failed for {name} (id={player_id}): {e}", file=sys.stderr)

               try:
                   last5 = fetch_last5(player_id)
               except Exception as e:
                   print(f"[WARN] last5 stats failed for {name} (id={player_id}): {e}", file=sys.stderr)

           # ---- Build stat object with safe defaults ----
           games = season_avg.get("games_played", 0) if season_avg else 0
           min_val = parse_minutes(season_avg.get("min")) if season_avg else 0.0

           pts = float(season_avg.get("pts", 0.0)) if season_avg else 0.0
           reb = float(season_avg.get("reb", 0.0)) if season_avg else 0.0
           ast = float(season_avg.get("ast", 0.0)) if season_avg else 0.0

           fg_pct = season_avg.get("fg_pct") if season_avg else None
           fg3_pct = season_avg.get("fg3_pct") if season_avg else None
           ft_pct = season_avg.get("ft_pct") if season_avg else None

           last5_pts = last5["pts"] if last5 else 0.0
           last5_reb = last5["reb"] if last5 else 0.0
           last5_ast = last5["ast"] if last5 else 0.0

           opp_team = opponents.get(team_code)

           final[name] = {
               "team": team_code,

               # Season context
               "season": SEASON,
               "games": games,
               "min": min_val,

               # Per-game season averages
               "pts": pts,
               "reb": reb,
               "ast": ast,
               "fg_pct": fg_pct,
               "fg3_pct": fg3_pct,
               "ft_pct": ft_pct,

               # Last-5 rolling averages
               "last5_pts": last5_pts,
               "last5_reb": last5_reb,
               "last5_ast": last5_ast,

               # Matchup fields (from your schedule.json – we only know opponent)
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

               # Fields your UI expects but BDL doesn't provide natively
               "usage": 0.0,
               "pace": None,
           }

   if missing:
       print("\n[INFO] Players not matched between rosters.json and BallDontLie:", file=sys.stderr)
       for name, team in missing:
           print(f"  - {name} ({team})", file=sys.stderr)

   print(f"\nBuilt stats for {len(final)} players.", file=sys.stderr)
   return final


def main():
   print("Building BallDontLie-based player_stats.json…", file=sys.stderr)
   stats = build_player_stats()

   with open("player_stats.json", "w", encoding="utf-8") as f:
       json.dump(stats, f, indent=2, sort_keys=True)

   print(f"Wrote player_stats.json with {len(stats)} players.", file=sys.stderr)


if __name__ == "__main__":
   main()
