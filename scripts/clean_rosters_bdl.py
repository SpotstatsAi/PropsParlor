#!/usr/bin/env python3
"""
Clean rosters.json so it only contains players that exist in BallDontLie.

- Reads rosters.json
- Calls BDL /players to get the full player list
- Normalizes names the same way as build_player_stats_bdl.py
- Drops any roster names that don't match a BDL player
- Writes:
    rosters_cleaned.json   -> filtered rosters
    rosters_unmatched.json -> players removed, with team info

Env:
  BALLDONTLIE_API_KEY  -> your BDL key (same as the stats builder)
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


def bdl_get(path: str, params: dict | None = None) -> dict:
    """Basic GET wrapper with retries."""
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
            print(f"[bdl_get] ERROR ({attempt+1}/3) on {url}: {e}", file=sys.stderr)
            if attempt == 2:
                raise
            sleep(1.5)

    raise RuntimeError("bdl_get: exhausted retries")


def norm_name(name: str) -> str:
    """Same normalization logic as the builder script."""
    return (
        name.lower()
        .replace(".", "")
        .replace("'", "")
        .replace("-", " ")
        .strip()
    )


def fetch_players_index() -> dict:
    """
    Build mapping normalized_name -> BDL player object
    using /players with pagination.
    """
    print("Fetching BallDontLie players index...", file=sys.stderr)
    players_by_name: dict[str, dict] = {}

    page = 1
    per_page = 100

    while True:
        data = bdl_get("players", params={"page": page, "per_page": per_page})
        players = data.get("data", [])
        if not players:
            break

        for p in players:
            full_name = f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip()
            key = norm_name(full_name)
            players_by_name[key] = {
                "id": p["id"],
                "full_name": full_name,
                "team": (p.get("team") or {}).get("abbreviation"),
            }

        meta = data.get("meta", {})
        total_pages = meta.get("total_pages", page)
        print(f"  players page {page}/{total_pages}", file=sys.stderr)

        if page >= total_pages:
            break
        page += 1

    print(f"Indexed {len(players_by_name)} BDL players.", file=sys.stderr)
    return players_by_name


def main():
    # Load current rosters
    with open("rosters.json", "r", encoding="utf-8") as f:
        rosters = json.load(f)

    players_index = fetch_players_index()

    cleaned: dict[str, list[str]] = {}
    unmatched: list[dict] = []

    for team, plist in rosters.items():
        keep_list: list[str] = []
        for name in plist:
            key = norm_name(name)
            if key in players_index:
                keep_list.append(name)
            else:
                unmatched.append({"team": team, "name": name})
        cleaned[team] = keep_list

    # Write outputs
    with open("rosters_cleaned.json", "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, sort_keys=True)

    with open("rosters_unmatched.json", "w", encoding="utf-8") as f:
        json.dump(unmatched, f, indent=2)

    # Summary
    total_before = sum(len(v) for v in rosters.values())
    total_after = sum(len(v) for v in cleaned.values())
    print(f"Total players before: {total_before}", file=sys.stderr)
    print(f"Total players after:  {total_after}", file=sys.stderr)
    print(f"Removed: {total_before - total_after}", file=sys.stderr)
    print("Wrote rosters_cleaned.json and rosters_unmatched.json", file=sys.stderr)


if __name__ == "__main__":
    main()
