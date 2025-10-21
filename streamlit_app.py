# is_ai_crawling_my_website.py

import streamlit as st
import pandas as pd
import requests
from io import StringIO

# ----------------------------
# Écran d'accueil
# ----------------------------
st.set_page_config(page_title="Is AI Crawling My Website?", layout="wide")
st.title("Is AI Crawling My Website?")
st.write(
    "This application detects the presence of AI bots in your server logs. "
    "Upload a log file, and it will check if known AI crawlers accessed your website."
)

# ----------------------------
# Upload du fichier log
# ----------------------------
uploaded_file = st.file_uploader(
    "Upload your log file (max 50MB, any text format, uncompressed)",
    type=None,
    accept_multiple_files=False
)

if uploaded_file is not None:
    # Vérification de la taille du fichier
    if uploaded_file.size > 50 * 1024 * 1024:  # 50 Mo
        st.error("File too large! Please upload a file smaller than 50MB.")
    else:
        # Lire le contenu du fichier
        log_content = uploaded_file.read().decode("utf-8", errors="ignore")
        log_lines = log_content.splitlines()  # On sépare les lignes

        st.success(f"Successfully loaded {len(log_lines)} lines from the log file.")

        # ----------------------------
        # Téléchargement du fichier de référence des crawlers IA
        # ----------------------------
        url_crawlers = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.csv"
        response = requests.get(url_crawlers)

        if response.status_code != 200:
            st.error("Unable to download AI crawler database.")
        else:
            # Charger le CSV dans un DataFrame
            csv_data = StringIO(response.text)
            crawlers_df = pd.read_csv(csv_data, sep=";", header=None, names=["name", "user_agent", "ip_start"])

            # Initialiser un dictionnaire pour compter les occurrences
            crawler_counts = {row["name"]: 0 for index, row in crawlers_df.iterrows()}

            # ----------------------------
            # Parcourir le fichier log et chercher les user-agents
            # ----------------------------
            st.info("Scanning logs for AI crawler user-agents...")

            for line in log_lines:
                for index, row in crawlers_df.iterrows():
                    # Vérifie si le user-agent est présent dans la ligne
                    if row["user_agent"] in line:
                        crawler_counts[row["name"]] += 1

            # ----------------------------
            # Affichage des résultats
            # ----------------------------
            st.subheader("Detected AI crawlers in your logs:")
            result_df = pd.DataFrame(list(crawler_counts.items()), columns=["AI Crawler", "Occurrences"])
            result_df = result_df[result_df["Occurrences"] > 0]  # Ne montrer que les crawlers détectés

            if not result_df.empty:
                st.dataframe(result_df.sort_values(by="Occurrences", ascending=False))
            else:
                st.write("No AI crawlers detected in the uploaded log file.")
