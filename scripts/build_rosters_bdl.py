# -*- coding: utf-8 -*-
import os
import json
import requests

API_BASE = "https://api.balldontlie.io/v1"
API_KEY = os.environ.get("BDL_API_KEY")

if not API_KEY:
    raise SystemExit("BDL_API_KEY env var is not set")

def fetch_active_players():
    players = []
    cursor = None

    while True:
        params = {
            "per_page": 100,
        }
        if cursor is not None:
            params["cursor"] = cursor

        resp = requests.get(
            f"{API_BASE}/players/active",
            headers={"Authorization": API_KEY},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        players.extend(data.get("data", []))

        meta = data.get("meta", {}) or {}
        cursor = meta.get("next_cursor")
        if not cursor:
            break

        print(f"Fetched {len(players)} players so far… cursor={cursor}")

    return players

def transform_players(raw_players):
    out = []
    for p in raw_players:
        team = p.get("team") or {}
        first = (p.get("first_name") or "").strip()
        last = (p.get("last_name") or "").strip()
        full_name = f"{first} {last}".strip()

        out.append({
            "id": p.get("id"),
            "name": full_name,
            "first_name": first,
            "last_name": last,
            "team": team.get("abbreviation"),
            "pos": p.get("position"),
            "height": p.get("height"),
            "weight": p.get("weight"),
            "jersey": p.get("jersey_number"),
        })
    return out

def main():
    print("Fetching active players from Balldontlie…")
    raw_players = fetch_active_players()
    print(f"Total raw players fetched: {len(raw_players)}")

    players = transform_players(raw_players)
    players.sort(key=lambda x: (x.get("team") or "", x.get("name") or ""))

    with open("rosters.json", "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(players)} players to rosters.json")

if __name__ == "__main__":
    main()
