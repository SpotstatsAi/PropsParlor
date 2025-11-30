import requests
import json
from datetime import datetime

BDL_API_KEY = "YOUR_PREMIUM_BDL_API_KEY"
BASE_URL = "https://api.balldontlie.io/v1"


def bdl_get(endpoint, params=None):
   """Universal BDL GET helper"""
   headers = {"Authorization": f"Bearer {BDL_API_KEY}"}

   r = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params)
   r.raise_for_status()
   return r.json()


def load_rosters():
   """Load rosters.json from repo root"""
   with open("rosters.json", "r", encoding="utf-8") as f:
       return json.load(f)


def load_schedule():
   """Load schedule.json from repo root"""
   with open("schedule.json", "r", encoding="utf-8") as f:
       return json.load(f)


def get_season_averages():
   """Pull full league season averages using BDL Premium"""
   print("Fetching SEASON AVERAGES...")
   averages = {}
   page = 1

   while True:
       data = bdl_get("season_averages", params={"page": page, "per_page": 100})
       if "data" not in data or len(data["data"]) == 0:
           break

       for p in data["data"]:
           averages[p["player_id"]] = p

       page += 1

   return averages


def build_player_map():
   """Retrieve league player directory for ID → name mapping"""
   print("Fetching PLAYER DIRECTORY...")
   player_map = {}
   page = 1

   while True:
       data = bdl_get("players", params={"page": page, "per_page": 100})
       if len(data["data"]) == 0:
           break

       for item in data["data"]:
           pid = item["id"]
           name = item["first_name"] + " " + item["last_name"]
           team = item["team"]["abbreviation"] if item["team"] else None

           player_map[pid] = {
               "name": name,
               "team": team
           }

       page += 1

   return player_map


def get_today_opponents(schedule):
   """Reads schedule.json for today's matchups"""
   today = datetime.now().strftime("%Y-%m-%d")
   games_today = schedule.get(today, [])

   opp_lookup = {}

   for g in games_today:
       home = g["home_team"]
       away = g["away_team"]

       opp_lookup[home] = {"opp": away}
       opp_lookup[away] = {"opp": home}

   return opp_lookup


def build_player_stats():
   rosters = load_rosters()
   schedule = load_schedule()

   season_avgs = get_season_averages()
   directory = build_player_map()
   today_opponents = get_today_opponents(schedule)

   player_stats = {}

   print("Building player_stats.json...")

   for team, players in rosters.items():
       for player_name in players:

           # Match directory data → get player_id
           pid = None
           player_team = None

           for d_id, d in directory.items():
               if d["name"].lower().strip() == player_name.lower().strip():
                   pid = d_id
                   player_team = d["team"]
                   break

           if pid is None:
               # Unknown player → blank record
               player_stats[player_name] = {
                   "pts": 0,
                   "reb": 0,
                   "ast": 0,
                   "stl": 0,
                   "blk": 0,
                   "fg_pct": 0,
                   "ft_pct": 0,
                   "fg3_pct": 0,
                   "games": 0,
                   "team": team,
                   "opponent": None,
               }
               continue

           # Try to pull season averages
           avg = season_avgs.get(pid, {})

           player_stats[player_name] = {
               "pts": avg.get("pts", 0),
               "reb": avg.get("reb", 0),
               "ast": avg.get("ast", 0),
               "stl": avg.get("stl", 0),
               "blk": avg.get("blk", 0),
               "fg_pct": avg.get("fg_pct", 0),
               "fg3_pct": avg.get("fg3_pct", 0),
               "ft_pct": avg.get("ft_pct", 0),
               "games": avg.get("games_played", 0),

               # Base context
               "team": team,
               "opponent": today_opponents.get(team, {}).get("opp"),
           }

   return player_stats


def main():
   stats = build_player_stats()

   with open("player_stats.json", "w", encoding="utf-8") as f:
       json.dump(stats, f, indent=2)

   print("SUCCESS: player_stats.json updated")


if __name__ == "__main__":
   main()
