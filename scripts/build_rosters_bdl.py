#!/usr/bin/env python3
"""
build_rosters_bdl.py

Builds rosters.json from the BallDontLie API.

- Pulls ALL active NBA players from /v1/players
- Filters to the 30 NBA teams
- Writes rosters.json using EXACT team abbreviations your UI expects:
   {
     "ATL": ["Trae Young", ...],
     "BOS": [...],
     ...
   }

Environment:
 BALLDONTLIE_API_KEY  -> your BallDontLie premium API key
"""

import json
import os
import sys
from time import sleep
import requests

BDL_BASE = "https://api.balldontlie.io/v1"

API_KEY = os.getenv("BALLDONTLIE_API_KEY", "").strip()
if not API_KEY:
   print("ERROR: BALLDONTLIE_API_KEY is not set", file=sys.stderr)
   sys.exit(1)

# 30 NBA team abbreviations used by BDL
NBA_TEAMS = {
   "ATL","BOS","BKN","CHA","CHI","CLE",
   "DAL","DEN","DET","GSW","HOU","IND",
   "LAC","LAL","MEM","MIA","MIL","MIN",
   "NOP","NYK","OKC","ORL","PHI","PHX",
   "POR","SAC","SAS","TOR","UTA","WAS"
}

def bdl_get(path, params=None):
   """BallDontLie GET wrapper with retries."""
   url = f"{BDL_BASE}/{path}"
   headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

   for attempt in range(3):
       try:
           r = requests.get(url, headers=headers, params=params, timeout=30)
           r.raise_for_status()
           return r.json()
       except Exception as e:
           print(f"[bdl_get] ERROR attempt {attempt+1}/3: {e}", file=sys.stderr)
           if attempt == 2:
               raise
           sleep(1.2)

def fetch_rosters_from_bdl():
   print("Fetching players from BallDontLie...", file=sys.stderr)

   rosters = {team: [] for team in NBA_TEAMS}

   page = 1
   per_page = 100

   while True:
       data = bdl_get("players", {"page": page, "per_page": per_page, "active": "true"})
       players = data.get("data", [])
       meta = data.get("meta", {})
       total_pages = meta.get("total_pages", page)

       print(f"  players page {page}/{total_pages}", file=sys.stderr)

       if not players:
           break

       for p in players:
           team = p.get("team") or {}
           abbr = team.get("abbreviation")
           if abbr not in NBA_TEAMS:
               continue

           first = (p.get("first_name") or "").strip()
           last = (p.get("last_name") or "").strip()
           full = f"{first} {last}".strip()

           if full and full not in rosters[abbr]:
               rosters[abbr].append(full)

       if page >= total_pages:
           break
       page += 1

   # Sort names for consistency
   for t in rosters:
       rosters[t].sort()

   return rosters

def main():
   print("Building rosters.json from BallDontLie...", file=sys.stderr)
   rosters = fetch_rosters_from_bdl()

   with open("rosters.json", "w", encoding="utf-8") as f:
       json.dump(rosters, f, indent=2, sort_keys=True)

   total = sum(len(v) for v in rosters.values())
   print(f"Wrote rosters.json with {total} total players.", file=sys.stderr)

if __name__ == "__main__":
   main()
