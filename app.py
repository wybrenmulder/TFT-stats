from flask import Flask, render_template, request, jsonify
from api_key import API_KEY
from requests import get
from collections import defaultdict

app = Flask(__name__)

REGION_DATA = {
    "KR": ("kr", "asia"),
    "EUW": ("euw1", "europe"),
    "VN": ("vn", "asia"),
    "EUNE": ("eun1", "europe"),
    "BR": ("br1", "americas"),
    "NA": ("na1", "americas"),
    "LAN": ("la1", "americas"),
    "TR": ("tr1", "europe"),
    "LAS": ("la2", "americas"),
    "PH": ("ph", "sea"),
    "OCE": ("oc1", "sea"),
    "JP": ("jp1", "asia"),
}

# TFT Set 15 units keyed by champion name
UNIT_ID_MAP = {
    # 1-cost units
    "Aatrox": {"id": "15a", "cost": 1},
    "Ezreal": {"id": "168", "cost": 1},
    "Garen": {"id": "16a", "cost": 1},
    "Gnar": {"id": "018", "cost": 1},
    "Kalista": {"id": "173", "cost": 1},
    "Kayle": {"id": "175", "cost": 1},
    "Kennen": {"id": "176", "cost": 1},
    "Lucian": {"id": "017", "cost": 1},
    "Malphite": {"id": "17d", "cost": 1},
    "Naafiri": {"id": "180", "cost": 1},
    "Rell": {"id": "185", "cost": 1},
    "Sivir": {"id": "01b", "cost": 1},
    "Syndra": {"id": "18d", "cost": 1},
    "Zac": {"id": "197", "cost": 1},

    # 2-cost units
    "Dr. Mundo": {"id": "014", "cost": 2},
    "Gangplank": {"id": "016", "cost": 2},
    "Janna": {"id": "16c", "cost": 2},
    "Jhin": {"id": "16f", "cost": 2},
    "Kai'Sa": {"id": "172", "cost": 2},
    "Katarina": {"id": "174", "cost": 2},
    "Kobuko": {"id": "177", "cost": 2},
    "Lux": {"id": "17b", "cost": 2},
    "Rakan": {"id": "184", "cost": 2},
    "Shen": {"id": "00d", "cost": 2},
    "Vi": {"id": "01a", "cost": 2},
    "Xayah": {"id": "192", "cost": 2},
    "Xin Zhao": {"id": "193", "cost": 2},

    # 3-cost units
    "Ahri": {"id": "15b", "cost": 3},
    "Caitlyn": {"id": "164", "cost": 3},
    "Darius": {"id": "166", "cost": 3},
    "Jayce": {"id": "16e", "cost": 3},
    "Lulu": {"id": "17a", "cost": 3},
    "Malzahar": {"id": "17e", "cost": 3},
    "Neeko": {"id": "01d", "cost": 3},
    "Senna": {"id": "013", "cost": 3},
    "Swain": {"id": "18c", "cost": 3},
    "Udyr": {"id": "18e", "cost": 3},
    "Viego": {"id": "191", "cost": 3},
    "Yasuo": {"id": "194", "cost": 3},
    "Ziggs": {"id": "198", "cost": 3},

    # 4-cost units
    "Akali": {"id": "15c", "cost": 4},
    "Ashe": {"id": "15e", "cost": 4},
    "Jarvan IV": {"id": "16d", "cost": 4},
    "Jinx": {"id": "170", "cost": 4},
    "K'Sante": {"id": "171", "cost": 4},
    "Karma": {"id": "019", "cost": 4},
    "Leona": {"id": "179", "cost": 4},
    "Poppy": {"id": "182", "cost": 4},
    "Ryze": {"id": "187", "cost": 4},
    "Samira": {"id": "188", "cost": 4},
    "Sett": {"id": "18a", "cost": 4},
    "Volibear": {"id": "199", "cost": 4},
    "Yuumi": {"id": "196", "cost": 4},

    # 5-cost units
    "Braum": {"id": "163", "cost": 5},
    "Gwen": {"id": "16b", "cost": 5},
    "Lee Sin": {"id": "178", "cost": 5},
    "Seraphine": {"id": "189", "cost": 5},
    "Twisted Fate": {"id": "01c", "cost": 5},
    "Varus": {"id": "190", "cost": 5},
    "Yone": {"id": "195", "cost": 5},
    "Zyra": {"id": "01e", "cost": 5},
}


def get_puuid(game_name, tag_line):
    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {"X-Riot-Token": API_KEY}
    response = get(url, headers=headers)
    return response.json()["puuid"] if response.status_code == 200 else None


def get_summoner_region(puuid):
    for (server, match_region) in REGION_DATA.values():
        if fetch_summoner_info(server, puuid):
            return server, match_region
    return None, None


def fetch_summoner_info(server, puuid):
    url = f"https://{server}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    headers = {"X-Riot-Token": API_KEY}
    response = get(url, headers=headers)
    return response.json() if response.status_code == 200 else None


def get_match_history(puuid, region, count=5):
    url = f"https://{region}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids?count={count}"
    headers = {"X-Riot-Token": API_KEY}
    response = get(url, headers=headers)
    return response.json() if response.status_code == 200 else None


def get_match_details(match_id, region):
    url = f"https://{region}.api.riotgames.com/tft/match/v1/matches/{match_id}"
    headers = {"X-Riot-Token": API_KEY}
    response = get(url, headers=headers)
    if response.status_code != 200:
        return None
    data = response.json()
    participants = data.get("info", {}).get("participants", [])
    if not participants:
        return None

    game_mode = data["info"].get("tft_game_type", "standard")
    return process_participants(participants, game_mode)


def process_participants(participants, game_mode="standard"):
    """Process participants for TFT matches. Handles solo or pairs (doubles)."""
    if game_mode in ["pairs", "duo"]:  # Combine by partner_group_id
        teams = {}
        for player in participants:
            group_id = player["partner_group_id"]
            if group_id not in teams:
                teams[group_id] = {"placement": player["placement"], "players": []}
            teams[group_id]["players"].append(format_player_info(player))
            teams[group_id]["placement"] = min(teams[group_id]["placement"], player["placement"])
        # Sort teams by placement
        return dict(sorted(teams.items(), key=lambda x: x[1]["placement"]))
    else:  # Solo
        players = [format_player_info(p) for p in participants]
        return sorted(players, key=lambda x: x["placement"])


def format_player_info(player):
    """Format a TFT Set 15 player into a clean dictionary."""
    augments = player.get("augments", [])
    traits = [
        f"{t['name']} (Tier {t['tier_current']})"
        for t in player.get("traits", [])
        if t.get("tier_current", 0) > 0
    ]
    units = []
    for u in player.get("units", []):
        items = ", ".join(u.get("itemNames", [])) if u.get("itemNames") else "No items"
        units.append(f"{u['character_id']} ★{u['tier']} [{items}]")

    return {
        "summoner_name": f"{player.get('riotIdGameName', 'Unknown')}#{player.get('riotIdTagline', '0000')}",
        "placement": player["placement"],
        "level": player["level"],
        "gold_left": player["gold_left"],
        "last_round": player["last_round"],
        "time_eliminated": int(player["time_eliminated"]),
        "total_damage_to_players": player.get("total_damage_to_players", 0),
        "augments": ", ".join(augments) if augments else "None",
        "traits": ", ".join(traits) if traits else "None",
        "units": "; ".join(units) if units else "None",
    }


@app.route("/", methods=["GET"])
def home():
    return render_template("search.html")


@app.route("/search", methods=["POST"])
def search():
    game_name = request.form.get("game_name")
    tag_line = request.form.get("tag_line")
    if not game_name or not tag_line:
        return "Error: Missing game name or tag line."

    puuid = get_puuid(game_name, tag_line)
    if not puuid:
        return "Error retrieving player data."

    summoner_region, match_region = get_summoner_region(puuid)
    if not summoner_region or not match_region:
        return "Error: Could not determine the correct region."

    match_ids = get_match_history(puuid, match_region)
    if not match_ids:
        return "No match history available."

    matches = []
    for match_id in match_ids:
        match_data = get_match_details(match_id, match_region)
        if match_data:
            if isinstance(match_data, list):
                matches.append({"match_id": match_id, "players": match_data})
            else:
                matches.append({"match_id": match_id, "teams": match_data})

    return render_template("tft_matches.html", tft_matches=matches)


@app.route("/team_builder")
def team_builder():
    cost_groups = defaultdict(list)
    for champ_name, info in UNIT_ID_MAP.items():
        cost_groups[info['cost']].append(champ_name)  # <-- use champ_name, not info['name']
    
    # Sort each group alphabetically
    for cost in cost_groups:
        cost_groups[cost].sort()

    return render_template("team_builder.html", cost_groups=cost_groups)


@app.route("/generate_code", methods=["POST"])
def generate_code():
    selected_units = request.json.get("units", [])[:10]  # max 10 units
    unit_codes = [UNIT_ID_MAP[champ]['id'] for champ in selected_units if champ in UNIT_ID_MAP]

    # Pad to 10 units
    while len(unit_codes) < 10:
        unit_codes.append("000")

    # No spaces
    team_code = "02" + "".join(unit_codes) + "TFTSet15"
    return jsonify({"team_code": team_code})


if __name__ == "__main__":
    app.run(debug=True)
