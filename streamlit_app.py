# is_ai_crawling_my_website.py

import streamlit as st
import pandas as pd
import requests
import re
import csv

# ----------------------------
# FONCTION POUR CHARGER LE JSON DES ROBOTS IA
# ----------------------------
# @st.cache_data  # commenter pour dev, décommenter pour production
def load_ai_robots(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Impossible de charger la liste des robots IA.")
        return []

# ----------------------------
# FONCTION POUR ANALYSER LES LOGS ET COMPTER LES OCCURRENCES
# ----------------------------
def analyze_logs(lines, ai_robots):
    counts = {robot['name']: 0 for robot in ai_robots}
    for line in lines:
        line_str = line.decode('utf-8', errors='ignore')
        for robot in ai_robots:
            if robot['user-agent'] in line_str:
                counts[robot['name']] += 1
    return counts

# ----------------------------
# FONCTION POUR EXTRAIRE LES LIGNES DES ROBOTS IA
# ----------------------------
def extract_ai_lines(lines, ai_robots):
    pattern_ip = r'\b\d{1,3}(?:\.\d{1,3}){3}\b'
    pattern_status = r'\b([2-5]\d{2})\b'
    pattern_get_path = r'\"(?:GET|POST) ([^ ]+)'
    pattern_user_agent = r'\"([^\"]*)\"$'

    results = []

    for line in lines:
        line_str = line.decode('utf-8', errors='ignore')
        for robot in ai_robots:
            if robot['user-agent'] in line_str:
                ip_match = re.search(pattern_ip, line_str)
                path_match = re.search(pattern_get_path, line_str)
                status_match = re.search(pattern_status, line_str)
                ua_match = re.search(pattern_user_agent, line_str)

                if ip_match and path_match and status_match and ua_match:
                    results.append({
                        "IP": ip_match.group(0),
                        "Path": path_match.group(1),
                        "Status": status_match.group(1),
                        "User-Agent": ua_match.group(1),
                        "Robot Name": robot['name']
                    })
                break  # ligne trouvée, pas besoin de vérifier les autres robots

    df = pd.DataFrame(results)
    return df

# ----------------------------
# INTERFACE STREAMLIT
# ----------------------------
st.title("Is AI crawling my website?")
st.markdown("""
This application helps you detect AI crawlers in your website logs.  
Upload your log file (max 50 MB), and it will search for known AI bots.
""")

JSON_URL = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.json"
ai_robots = load_ai_robots(JSON_URL)

uploaded_file = st.file_uploader(
    "Upload your log file (max 50 MB, uncompressed)", 
    type=None
)

if uploaded_file is not None:
    if uploaded_file.size > 50 * 1024 * 1024:
        st.error("File too large! Please upload a file smaller than 50 MB.")
    else:
        lines = uploaded_file.readlines()

        # Analyse des occurrences
        counts = analyze_logs(lines, ai_robots)
        df_results = pd.DataFrame(list(counts.items()), columns=["AI Robot Name", "Occurrences"])
        df_results = df_results.sort_values(by="Occurrences", ascending=False).reset_index(drop=True)

        st.subheader("Detected AI Crawlers")
        st.table(df_results)

        # Extraction des lignes correspondant aux robots IA
        df_ai_lines = extract_ai_lines(lines, ai_robots)

        if not df_ai_lines.empty:
            st.subheader("AI Lines Found")
            st.dataframe(df_ai_lines, use_container_width=True)

            # Téléchargement CSV
            csv_data = df_ai_lines.to_csv(
                index=False,
                sep=',',
                quoting=csv.QUOTE_ALL  # entoure toutes les colonnes de guillemets
            )

            st.download_button(
                label="Download AI lines as CSV",
                data=csv_data,
                file_name="ai_lines.csv",
                mime="text/csv"
            )
        else:
            st.success("No AI crawler lines found in your logs.")
