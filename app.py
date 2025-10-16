import os
import json
import sqlite3
from collections import defaultdict
from requests import get
from flask import Flask, render_template, request, jsonify
from api_key import API_KEY

app = Flask(__name__)

# ---------------------------
# CONFIG: external data files
# ---------------------------
DATA_DIR = os.path.join("static", "data")
REGION_DATA_FILE = os.path.join(DATA_DIR, "region_data.json")
UNIT_DATA_FILE = os.path.join(DATA_DIR, "unit_data.json")
TRAIT_DATA_FILE = os.path.join(DATA_DIR, "trait_data.json")

# Check files exist
for file_path in [REGION_DATA_FILE, UNIT_DATA_FILE, TRAIT_DATA_FILE]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Missing {file_path}")

# Load data
with open(REGION_DATA_FILE, "r", encoding="utf-8") as f:
    REGION_DATA = json.load(f)

with open(UNIT_DATA_FILE, "r", encoding="utf-8") as f:
    raw_unit_data = json.load(f)

with open(TRAIT_DATA_FILE, "r", encoding="utf-8") as f:
    TRAIT_DATA = json.load(f)

# ---------------------------
# UNIT MAPS
# ---------------------------
UNIT_ID_MAP = {}
for name, data in raw_unit_data.items():
    api_name = data.get("api_name", name)
    UNIT_ID_MAP[name] = {"id": data["id"], "cost": data["cost"], "api_name": api_name}

# ---------------------------
# DB SETUP
# ---------------------------
DB_FILE = "snapshots.db"

def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE snapshots (
                puuid TEXT,
                queue_type TEXT,
                lp INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

init_db()

# ---------------------------
# RIOT API HELPERS
# ---------------------------
def get_puuid(game_name: str, tag_line: str):
    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {"X-Riot-Token": API_KEY}
    r = get(url, headers=headers)
    return r.json().get("puuid") if r.status_code == 200 else None

def fetch_summoner_info(server: str, puuid: str):
    url = f"https://{server}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    headers = {"X-Riot-Token": API_KEY}
    r = get(url, headers=headers)
    return r.json() if r.status_code == 200 else None

def get_summoner_region(puuid: str):
    for short, (server, match_region) in REGION_DATA.items():
        if fetch_summoner_info(server, puuid):
            return server, match_region
    return None, None

def get_match_history(puuid: str, region: str, count: int = 5):
    url = f"https://{region}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids?count={count}"
    headers = {"X-Riot-Token": API_KEY}
    r = get(url, headers=headers)
    return r.json() if r.status_code == 200 else None

def get_match_details(match_id: str, region: str):
    url = f"https://{region}.api.riotgames.com/tft/match/v1/matches/{match_id}"
    headers = {"X-Riot-Token": API_KEY}
    r = get(url, headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    participants = data.get("info", {}).get("participants", [])
    if not participants:
        return None
    game_mode = data["info"].get("tft_game_type", "standard")
    return process_participants(participants, game_mode)

# ---------------------------
# PLAYER FORMATTING
# ---------------------------
def format_player_info(player: dict):
    traits = player.get("traits", []) or []
    units = [
        {
            "name": u["character_id"],
            "tier": u["tier"],
            "item_list": u.get("itemNames", [])
        }
        for u in player.get("units", [])
    ]
    summoner_name = f"{player.get('riotIdGameName', 'Unknown')}#{player.get('riotIdTagline', '0000')}"
    return {
        "summoner_name": summoner_name,
        "placement": player.get("placement", 0),
        "level": player.get("level", 0),
        "gold_left": player.get("gold_left", 0),
        "last_round": player.get("last_round", 0),
        "time_eliminated": int(player.get("time_eliminated", 0)),
        "total_damage_to_players": player.get("total_damage_to_players", 0),
        "traits": traits,
        "units": units,
    }

def process_participants(participants: list, game_mode: str = "standard"):
    if game_mode in ["pairs", "duo"]:
        teams = {}
        for p in participants:
            gid = p.get("partner_group_id")
            if gid not in teams:
                teams[gid] = {"placement": p.get("placement", 0), "players": []}
            teams[gid]["players"].append(format_player_info(p))
            teams[gid]["placement"] = min(teams[gid]["placement"], p.get("placement", 0))
        return dict(sorted(teams.items(), key=lambda x: x[1]["placement"]))
    else:
        players = [format_player_info(p) for p in participants]
        return sorted(players, key=lambda x: x.get("placement", 0))

# ---------------------------
# HELPER: UNIT DISPLAY NAME
# ---------------------------
def get_display_unit_name(api_name):
    for display_name, data in UNIT_ID_MAP.items():
        if data.get("api_name") == api_name:
            return display_name, data.get("cost", 1)
    return api_name, 1

# ---------------------------
# ROUTES
# ---------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/dashboard", methods=["POST"])
def dashboard():
    game_name = request.form.get("game_name")
    tag_line = request.form.get("tag_line")
    if not game_name or not tag_line:
        return "Missing game name or tag line.", 400

    puuid = get_puuid(game_name, tag_line)
    if not puuid:
        return "Error retrieving player data (puuid).", 400

    summoner_region, match_region = get_summoner_region(puuid)
    if not summoner_region or not match_region:
        return "Error: Could not determine region.", 400

    match_ids = get_match_history(puuid, match_region)
    if not match_ids:
        return "No match history available.", 404

    matches = []
    for mid in match_ids:
        md = get_match_details(mid, match_region)
        if md:
            if isinstance(md, list):
                matches.append({"match_id": mid, "players": md, "game_mode": "Standard"})
            else:
                matches.append({"match_id": mid, "teams": md, "game_mode": "Standard"})

    full_name = f"{game_name}#{tag_line}"
    for m in matches:
        found_player = None
        if m.get("players"):
            for p in m["players"]:
                if p.get("summoner_name", "") == full_name:
                    p["is_me"] = True
                    found_player = p
                else:
                    p["is_me"] = False
        if m.get("teams"):
            for team in m["teams"].values():
                for p in team.get("players", []):
                    if p.get("summoner_name", "") == full_name:
                        p["is_me"] = True
                        found_player = p
                    else:
                        p["is_me"] = p.get("is_me", False)
        m["my_player"] = found_player or (m.get("players")[0] if m.get("players") else next(iter(m.get("teams", {}).values()))["players"][0])

    return render_template(
        "dashboard.html",
        game_name=game_name,
        tag_line=tag_line,
        tft_matches=matches,
        UNIT_ID_MAP=UNIT_ID_MAP,
        TRAIT_DATA=TRAIT_DATA,  # <-- pass trait mapping
        get_display_unit_name=get_display_unit_name
    )

@app.route("/team_builder")
def team_builder():
    cost_groups = defaultdict(list)
    for champ, info in UNIT_ID_MAP.items():
        cost_groups[info["cost"]].append(champ)
    for cost in cost_groups:
        cost_groups[cost].sort()
    return render_template("team_builder.html", cost_groups=cost_groups)

@app.route("/generate_code", methods=["POST"])
def generate_code():
    selected_units = request.json.get("units", [])[:10]
    unit_codes = [UNIT_ID_MAP[c]["id"] for c in selected_units if c in UNIT_ID_MAP]
    while len(unit_codes) < 10:
        unit_codes.append("000")
    team_code = "02" + "".join(unit_codes) + "TFTSet15"
    return jsonify({"team_code": team_code})

# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
