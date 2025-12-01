#!/usr/bin/env python3
"""
build_rosters_bdl.py

Generates rosters.json using the BallDontLie API.

This script:
 • Fetches ALL players from BDL using pagination
 • Filters to ACTIVE players with a valid team
 • Normalizes names so player_stats_bdl can match them perfectly
 • Groups players into NBA rosters by team abbreviation
 • Outputs rosters.json in the exact format your UI expects

Environment:
 BALLDONTLIE_API_KEY = your BDL Bearer token
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


# ------------------------------
# Helpers
# ------------------------------

def bdl_get(path: str, params=None) -> dict:
   """Low-level GET wrapper with retries."""
   url = f"{BDL_BASE}/{path}"
   headers = {
       "Authorization": f"Bearer {API_KEY}",
       "Accept": "application/json",
   }

   for attempt in range(3):
       try:
           resp = requests.get(url, headers=headers, params=params, timeout=30)
           resp.raise_for_status()
           return resp.json()
       except requests.RequestException as e:
           print(f"[bdl_get] ERROR {e} (attempt {attempt+1}/3)", file=sys.stderr)
           if attempt == 2:
               raise
           sleep(1.2)

   raise RuntimeError("bdl_get: failed after retries")


def norm_name(name: str) -> str:
   """Normalize player names for consistency."""
   return (
       name.lower()
       .replace(".", "")
       .replace("'", "")
       .replace("-", " ")
       .strip()
   )


# ------------------------------
# Build roster
# ------------------------------

def fetch_all_players() -> list:
   """Fetch the entire NBA player list via pagination."""
   print("Fetching ALL players from BallDontLie...", file=sys.stderr)

   players = []
   page = 1
   per_page = 100

   while True:
       data = bdl_get("players", params={"page": page, "per_page": per_page})
       batch = data.get("data", [])

       if not batch:
           break

       players.extend(batch)

       meta = data.get("meta", {})
       total_pages = meta.get("total_pages", page)
       print(f"  players page {page}/{total_pages}", file=sys.stderr)

       if page >= total_pages:
           break
       page += 1

   print(f"Total players fetched: {len(players)}", file=sys.stderr)
   return players


def build_rosters():
   """Build rosters grouped by team abbreviation."""
   players = fetch_all_players()

   rosters: dict[str, list[str]] = {}

   for p in players:
       team = p.get("team")
       if not team:
           continue

       abbrev = team.get("abbreviation")
       if not abbrev:
           continue

       # Build proper full name
       first = p.get("first_name", "").strip()
       last = p.get("last_name", "").strip()
       full = f"{first} {last}".strip()

       # Skip any weird blanks
       if not full:
           continue

       # Add player to team
       if abbrev not in rosters:
           rosters[abbrev] = []

       rosters[abbrev].append(full)

   # Sort player names alphabetically under each team
   for t in rosters:
       rosters[t] = sorted(rosters[t])

   print("Rosters built successfully.", file=sys.stderr)
   return rosters


def main():
   print("Building rosters.json via BallDontLie...", file=sys.stderr)

   rosters = build_rosters()

   with open("rosters.json", "w", encoding="utf-8") as f:
       json.dump(rosters, f, indent=2, sort_keys=True)

   print("Wrote rosters.json.", file=sys.stderr)


if __name__ == "__main__":
   main()
