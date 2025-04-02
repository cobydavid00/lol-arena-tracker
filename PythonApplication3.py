import streamlit as st
import pandas as pd
import urllib.parse
import requests
from collections import defaultdict
import time

API_KEY = "RGAPI-f5f9d629-8e07-4efb-8406-f4ba1eaabd1d"
SLEEP_INTERVAL = 10

@st.cache_data

def safe_riot_get(url, sleep_interval=SLEEP_INTERVAL):
    while True:
        response = requests.get(url)
        if response.status_code == 200:
            return response
        else:
            time.sleep(sleep_interval)


def get_puuid_from_riot_id(game_name, tag_line):
    encoded_name = urllib.parse.quote(game_name)
    encoded_tag = urllib.parse.quote(tag_line)
    url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{encoded_name}/{encoded_tag}?api_key={API_KEY}"
    response = safe_riot_get(url)
    data = response.json()
    return data.get("puuid")


def get_all_arena_match_ids(puuid):
    all_matches = []
    start = 0
    count = 100
    while True:
        url = (
            f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
            f"?queue=1700&start={start}&count={count}&api_key={API_KEY}"
        )
        response = safe_riot_get(url)
        match_ids = response.json()
        if not match_ids:
            break
        all_matches.extend(match_ids)
        start += count
    return all_matches


def get_arena_stats_for_matches(puuid, match_ids):
    arena_data = []
    for match_id in match_ids:
        url = f"https://asia.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={API_KEY}"
        response = safe_riot_get(url)
        match_data = response.json()
        participants = match_data.get("info", {}).get("participants", [])
        for player in participants:
            if player.get("puuid") == puuid:
                arena_data.append({
                    "champion": player.get("championName"),
                    "placement": player.get("placement")
                })
                break
        time.sleep(0.1)
    return arena_data


def get_all_champions():
    url = "https://ddragon.leagueoflegends.com/cdn/15.7.1/data/en_US/champion.json"
    response = safe_riot_get(url)
    data = response.json()
    return list(data["data"].keys())


def analyze_arena_data(arena_data, all_champions):
    summary = []
    champ_matches = defaultdict(list)
    for record in arena_data:
        champ = record["champion"]
        placement = record["placement"]
        champ_matches[champ].append(placement)

    for champ in all_champions:
        placements = champ_matches.get(champ, [])
        num_games = len(placements)
        avg_rank = round(sum(placements) / num_games, 2) if placements else None
        got_rank1 = 1 in placements
        summary.append({
            "champion": champ,
            "games_played": num_games,
            "average_placement": avg_rank if avg_rank is not None else "-",
            "reached_rank_1": "Yes" if got_rank1 else "No",
            "all_placements": ", ".join(map(str, placements)) if placements else "-"
        })
    return pd.DataFrame(summary)


# --- Streamlit UI ---
st.title("LoL Arena Champion Stats Viewer")

riot_id = st.text_input("Enter your Riot ID (e.g. 탑입니다#원거리)")

if riot_id and "#" in riot_id:
    game_name, tag_line = riot_id.split("#")
    with st.spinner("Fetching your Arena stats..."):
        puuid = get_puuid_from_riot_id(game_name, tag_line)
        if puuid:
            match_ids = get_all_arena_match_ids(puuid)
            arena_results = get_arena_stats_for_matches(puuid, match_ids)
            all_champions = get_all_champions()
            summary_df = analyze_arena_data(arena_results, all_champions)

            st.success(f"Found {len(match_ids)} Arena matches!")
            st.dataframe(summary_df, use_container_width=True)

            csv = summary_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download as CSV", csv, "arena_champion_summary.csv", "text/csv")
        else:
            st.error("Could not fetch PUUID. Check your Riot ID.")
elif riot_id:
    st.warning("Please enter your Riot ID in the correct format: Name#Tag")
