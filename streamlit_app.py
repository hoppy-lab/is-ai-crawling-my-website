import streamlit as st
import pandas as pd
import requests
import json

# ----------------------------
# PAGE D'ACCUEIL
# ----------------------------
st.set_page_config(page_title="Is AI Crawling My Website?", layout="wide")

st.title("Is AI Crawling My Website?")
st.markdown(
    """
    This application allows you to detect the presence of AI crawlers in your server logs. 
    Upload your log file, and the app will check if known AI bots visited your website.
    """
)

# ----------------------------
# TELEVERSEMENT DU FICHIER DE LOG
# ----------------------------
uploaded_file = st.file_uploader(
    "Upload your log file (max 50 MB, uncompressed)", 
    type=None,  # tous types sauf compressés
    accept_multiple_files=False
)

if uploaded_file is not None:
    # Vérification de la taille
    if uploaded_file.size > 50 * 1024 * 1024:
        st.error("File is too large. Please upload a file smaller than 50 MB.")
    else:
        # ----------------------------
        # CHARGEMENT DU JSON DE ROBOTS IA
        # ----------------------------
        robots_url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.json"
        response = requests.get(robots_url)
        if response.status_code == 200:
            robots_data = response.json()
        else:
            st.error("Unable to fetch AI robots database.")
            st.stop()

        # ----------------------------
        # INITIALISATION DU DICTIONNAIRE DE COMPTE
        # ----------------------------
        robots_count = {robot["name"]: 0 for robots-ia in robots_data}

        # ----------------------------
        # LECTURE DU FICHIER DE LOG LIGNE PAR LIGNE
        # ----------------------------
        # Conversion en string pour parcourir ligne par ligne
        log_content = uploaded_file.read().decode("utf-8", errors="ignore")
        lines = log_content.splitlines()

        # ----------------------------
        # RECHERCHE DES USER-AGENTS DANS LES LOGS
        # ----------------------------
        for line in lines:
            for robots-ia in robots_data:
                user_agent = robots-ia["user-agent"]
                # Si le user-agent est trouvé dans la ligne, on incrémente le compteur
                if user_agent in line:
                    robots_count[robot["name"]] += 1

        # ----------------------------
        # AFFICHAGE DES RESULTATS
        # ----------------------------
        st.subheader("AI Crawlers Detected")
        result_df = pd.DataFrame(
            {
                "AI Bot Name": list(robots_count.keys()),
                "Occurrences in Logs": list(robots_count.values())
            }
        )

        # Affichage seulement des robots trouvés au moins une fois
        result_df = result_df[result_df["Occurrences in Logs"] > 0]

        if not result_df.empty:
            st.dataframe(result_df.reset_index(drop=True))
        else:
            st.success("No AI crawlers detected in your log file.")
