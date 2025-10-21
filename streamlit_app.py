# Importation des librairies nécessaires
import streamlit as st
import pandas as pd
import requests

# Titre et description de l'application
st.set_page_config(page_title="Is AI Crawling My Website?")
st.title("Is AI Crawling My Website?")
st.write(
    "This application helps you detect the presence of AI bots in your website logs. "
    "Upload a log file and the app will analyze it to check if any known AI crawlers visited your site."
)

# Section pour télécharger le fichier de log
st.header("Upload your log file")
uploaded_file = st.file_uploader(
    "Choose a log file (less than 50MB, uncompressed)",
    type=None,
    accept_multiple_files=False
)

if uploaded_file is not None:
    if uploaded_file.size > 50 * 1024 * 1024:
        st.error("File too large! Please upload a file smaller than 50MB.")
    else:
        # Lecture du fichier ligne par ligne
        log_lines = uploaded_file.read().decode("utf-8", errors="ignore").splitlines()
        st.info(f"Uploaded file contains {len(log_lines)} lines")

        # Téléchargement du fichier de référence contenant les robots IA
        robots_url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.txt"
        response = requests.get(robots_url)
        response.raise_for_status()

        # Préparation de la liste des robots IA
        robots_data = []
        for line in response.text.splitlines():
            parts = line.strip().split("\t")
            if len(parts) == 3:
                robots_data.append({
                    "name": parts[0],
                    "user_agent": parts[1],
                    "ip_prefix": parts[2]
                })

        # Création d'un dataframe pour organiser les résultats
        df_results = pd.DataFrame(robots_data)
        df_results["count_user_agent_ip"] = 0  # Initialisation du compteur

# Parcours de chaque ligne du log
for line in log_lines:
    for i, robot in enumerate(robots_data):
        # Vérifie si le user-agent est dans la ligne
        if robot["user_agent"] in line:
            # Vérifie que l'IP correspond au préfixe du robot
            # On suppose que l'adresse IP est en début de ligne ou quelque part dans la ligne
            # On recherche " IP_PREFIX" ou "IP_PREFIX." pour éviter les faux positifs
            if any(ip_candidate.startswith(robot["ip_prefix"]) for ip_candidate in line.split()):
                df_results.at[i, "count_user_agent_ip"] += 1


        # Groupement par user-agent pour éviter les doublons
        df_grouped = df_results.groupby("user_agent").agg({
            "count_user_agent_ip": "sum",
            "name": "first"
        }).reset_index()

        # Affichage des résultats
        st.header("Detected AI crawlers in your logs (User-Agent + IP)")
        st.dataframe(df_grouped[["name", "count_user_agent_ip"]].sort_values(
            by="count_user_agent_ip", ascending=False
        ))
