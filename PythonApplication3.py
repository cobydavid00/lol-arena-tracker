import streamlit as st
import pandas as pd
import urllib.parse
import requests
from collections import defaultdict
import time
import matplotlib.pyplot as plt

API_KEY = st.secrets["api"]["riot_key"]
SLEEP_INTERVAL = 10


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
                    "placement": player.get("placement"),
                    "match_id": match_id
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
st.set_page_config(page_title="LoL Arena Tracker", layout="wide")
st.title("📊 LoL Arena Champion Tracker")

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

            # 🔢 Compute overall stats
            all_placements = [record["placement"] for record in arena_results]
            total_games = len(all_placements)
            rank1_count = all_placements.count(1)
            top4_count = sum(1 for p in all_placements if p <= 4)
            avg_placement = round(sum(all_placements) / total_games, 2) if total_games else "-"
            rank1_rate = f"{(rank1_count / total_games * 100):.2f}%" if total_games else "-"
            top4_rate = f"{(top4_count / total_games * 100):.2f}%" if total_games else "-"

            # 📊 Show overall stats
            st.markdown("### 🧾 Overall Stats")
            st.markdown(f"- **Total games played:** {total_games}")
            st.markdown(f"- **Average placement (all games):** {avg_placement}")
            st.markdown(f"- **1st-place rate:** {rank1_rate}")
            st.markdown(f"- **Top-4 rate:** {top4_rate}")

            # 📈 Chart: placement over time
            st.markdown("### 📉 Placement Over Time")
            placement_df = pd.DataFrame({
                "match_index": list(range(1, total_games + 1)),
                "placement": all_placements
            })
            st.line_chart(placement_df.set_index("match_index"))

            # 📋 Champion Summary Table
            st.markdown("### 🧠 Champion Performance Summary")

            summary_df["average_placement_numeric"] = pd.to_numeric(summary_df["average_placement"], errors="coerce")
            sort_order = st.selectbox("Sort champions by average placement:", ["Lowest first", "Highest first"])
            ascending = (sort_order == "Lowest first")
            sorted_df = summary_df.sort_values(by="average_placement_numeric", ascending=ascending)

            st.dataframe(
                sorted_df.drop(columns=["average_placement_numeric"]),
                use_container_width=True
            )

            # 📁 Downloadable CSV
            csv = sorted_df.drop(columns=["average_placement_numeric"]).to_csv(index=False).encode('utf-8')
            st.download_button("Download as CSV", csv, "arena_champion_summary.csv", "text/csv")

        else:
            st.error("Could not fetch PUUID. Check your Riot ID.")
elif riot_id:
    st.warning("Please enter your Riot ID in the correct format: Name#Tag")
