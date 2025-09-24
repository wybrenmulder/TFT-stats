from pprint import pprint
from api_key import API_KEY
from requests import get

# Combined dictionary for both Summoner API server and Match History region
REGION_DATA = {
    "NA": ("na1", "americas"),
    "BR": ("br1", "americas"),
    "LAN": ("la1", "americas"),
    "LAS": ("la2", "americas"),
    "EUW": ("euw1", "europe"),
    "EUNE": ("eun1", "europe"),
    "TR": ("tr1", "europe"),
    "RU": ("ru", "europe"),
    "KR": ("kr", "asia"),
    "JP": ("jp1", "asia"),
    "OCE": ("oc1", "sea"),
}

TEAM_NAMES = {
    1: "Poro",
    2: "Minion",
    3: "Scuttle",
    4: "Krug",
    5: "Raptor",
    6: "Sentinel",
    7: "Wolf",
    8: "Gromp",
}


def get_puuid(game_name, tag_line):
    """Fetch PUUID using Riot ID (game name + tag)"""
    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {"X-Riot-Token": API_KEY}

    response = get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data["puuid"], data["gameName"], data["tagLine"]
    print_error(response)
    return None, None, None


def print_error(response):
    """Helper function to handle errors"""
    print(f"Error {response.status_code}: {response.text}")


def get_summoner_region(puuid):
    """Fetch Summoner Info using PUUID to determine the correct region"""
    for server, match_region in REGION_DATA.values():
        region = fetch_summoner_info(server, puuid)
        if region:
            print(f"Found summoner in region: {server.upper()}")
            return server, match_region
    print("Could not determine summoner's region.")
    return None, None


def fetch_summoner_info(server, puuid):
    """Helper to fetch the summoner info"""
    url = f"https://{server}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    headers = {"X-Riot-Token": API_KEY}
    response = get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    print_error(response)
    return None


def get_match_history(puuid, region, start=0, count=20):
    """Fetch recent match history using PUUID"""
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}"
    headers = {"X-Riot-Token": API_KEY}

    response = get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    print_error(response)
    return None


def get_match_details(match_id, region):
    """Fetch match details and check if it's a TFT game"""
    url = f"https://{region}.api.riotgames.com//tft/match/v1/matches/{match_id}"
    headers = {"X-Riot-Token": API_KEY}

    response = get(url, headers=headers)
    if response.status_code != 200:
        print_error(response)
        return False, None

    data = response.json()
    game_mode = data.get("info", {}).get("gameMode")
    if game_mode != "CHERRY":
        return False, None

    return True, process_participants(data.get("info", {}).get("participants", []))


def process_participants(participants):
    """Process participants and return teams with player info in a dictionary format"""
    teams = {}
    placements = {}

    for player in participants:
        summoner_name = (
            player.get("riotIdGameName", "Unknown")
            + "#"
            + player.get("riotIdTagline", "0000")
        )
        subteam_id = player.get("playerSubteamId", 0)  # Get the subteam ID
        placement = player.get("placement", 9)  # Get team placement (default to 9 if missing)

        augments = [
            player.get(f"playerAugment{i}", None) for i in range(1, 7)
        ]
        augments = [a for a in augments if a is not None]  # Remove None values
        augments_str = ", ".join(map(str, augments))  # Convert to string for display

        player_info = format_player_info(player, summoner_name, augments_str)

        team_name = TEAM_NAMES.get(subteam_id, f"Unknown Team {subteam_id}")  # Map to team name
        if team_name not in teams:
            teams[team_name] = []
            placements[team_name] = placement  # Store placement per team

        teams[team_name].append(player_info)

    return sort_teams(teams, placements)


def format_player_info(player, summoner_name, augments_str):
    """Format player info into a dictionary"""
    champion = player.get("championName", "Unknown")
    kills = player.get("kills", 0)
    deaths = player.get("deaths", 0)
    assists = player.get("assists", 0)
    total_damage = player.get("totalDamageDealtToChampions", 0)
    total_damage_taken = player.get("totalDamageTaken", 0)
    gold_earned = player.get("goldEarned", 0)

    kda = f"{kills}/{deaths}/{assists}"
    kill_participation = (kills + assists) / (kills + deaths + assists) * 100 if (kills + deaths + assists) > 0 else 0
    kda_ratio = f"{(kills + assists) / (deaths + 1):.2f}"  # Avoid divide by 0

    # Return player info as a dictionary
    return {
        "summoner_name": summoner_name,
        "champion": champion,
        "kda": kda,
        "kill_participation": kill_participation,
        "kda_ratio": kda_ratio,
        "total_damage": total_damage,
        "total_damage_taken": total_damage_taken,
        "gold_earned": gold_earned,
        "augments": augments_str
    }


def sort_teams(teams, placements):
    """Sort teams based on placement"""
    sorted_teams = sorted(teams.keys(), key=lambda t: placements[t])
    return {team: teams[team] for team in sorted_teams}


def main():
    game_name = "wybo"
    tag_line = "plstn"

    # Get PUUID
    puuid, actual_game_name, actual_tag_line = get_puuid(game_name, tag_line)
    if not puuid:
        print("Could not find PUUID. Check your game name and tagline.")
        return None

    # Determine the summoner's actual region
    summoner_region, match_region = get_summoner_region(puuid)
    if not summoner_region or not match_region:
        print("Could not determine the correct region.")
        return None

    # Get Match History
    match_ids = get_match_history(puuid, match_region)
    if not match_ids:
        print("Could not retrieve match history.")
        return None

    TFT_matches = []

    for match_id in match_ids:
        is_TFT, teams = get_match_details(match_id, match_region)
        if is_TFT:
            TFT_matches.append({"match_id": match_id, "teams": teams})

    if TFT_matches:
        return {"TFT_matches": TFT_matches}
    return {"message": "No recent TFT matches found."}


if __name__ == "__main__":
    data = main()
    pprint(data)
