def fetch_season_averages_for_season(season, player_ids, batch_size=50):
    print(f"Fetching season averages for season {season}...")
    season_map = {}

    ids = list(player_ids)
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        print(f"  batch {i // batch_size + 1}: {len(batch)} players")

        params = [("season", season)]
        for pid in batch:
            params.append(("player_ids[]", pid))

        resp = requests.get(
            f"{API_BASE.replace('/v1', '/v2')}/stats/season",
            headers={"Authorization": API_KEY},
            params=params,
            timeout=30,
        )

        if not resp.ok:
            raise RuntimeError(
                f"BDL GET /v2/stats/season failed ({resp.status_code}): {resp.text}"
            )

        data = resp.json()

        for entry in data.get("data", []):
            pid = entry.get("player_id")
            if pid is None:
                continue
            season_map[pid] = entry

    print(f"Season {season}: got averages for {len(season_map)} players")
    return season_map
