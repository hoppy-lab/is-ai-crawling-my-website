# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import requests

# -------------------------------------------------------------
# PAGE D'ACCUEIL
# -------------------------------------------------------------
st.set_page_config(page_title="Is AI Crawling My Website?", layout="wide")

# Titre de l'application
st.title("Is AI Crawling My Website?")

# Description
st.markdown("""
This application helps you detect the presence of AI crawlers in your website logs.
Upload a log file, and the app will search for known AI crawler user-agents.
""")

# -------------------------------------------------------------
# CHARGEMENT DU FICHIER JSON DES ROBOTS IA
# -------------------------------------------------------------
ROBOTS_JSON_URL = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.json"

@st.cache_data
def load_ai_robots(url):
    """
    Charge la liste des robots IA depuis un fichier JSON en ligne.
    """
    response = requests.get(url)
    response.raise_for_status()  # Pour s'assurer que le téléchargement s'est bien passé
    data = response.json()
    
    # Vérification si le JSON contient un champ "robots"
    if isinstance(data, dict) and "robots" in data:
        return data["robots"]
    else:
        return data  # sinon on suppose que c'est déjà une liste de robots


# Chargement des robots
ai_robots = load_ai_robots(ROBOTS_JSON_URL)


# Affichage détaillé de chaque entrée pour debug
st.subheader("Debug: Entries in ai_robots")
for i, robot in enumerate(ai_robots):
    st.write(f"Entry {i}: {robot} (type: {type(robot)})")

# -------------------------------------------------------------
# INTERFACE POUR UPLOAD DU FICHIER DE LOG
# -------------------------------------------------------------
uploaded_file = st.file_uploader(
    "Upload your website log file (max 50 MB, uncompressed)",
    type=None  # n'importe quel format
)

# Vérifie que l'utilisateur a bien uploadé un fichier
if uploaded_file is not None:
    # Limite de 50 Mo
    if uploaded_file.size > 50 * 1024 * 1024:
        st.error("File is too large! Maximum allowed size is 50 MB.")
    else:
        # On parcourt le fichier ligne par ligne
        counts = {robot['name']: 0 for robot in ai_robots}  # Initialisation du compteur
        
        # Décodage du fichier selon l'encodage le plus probable
        try:
            lines = uploaded_file.read().decode('utf-8').splitlines()
        except UnicodeDecodeError:
            lines = uploaded_file.read().decode('latin-1').splitlines()
        
        # Parcours de chaque ligne et recherche des user-agents
        for line in lines:
            for robot in ai_robots:
                if robot['user-agent'] in line:
                    counts[robot['name']] += 1
        
        # Transformation en DataFrame pour affichage
        df_counts = pd.DataFrame(list(counts.items()), columns=["AI Crawler", "Occurrences"])
        
        # Affichage du tableau
        st.subheader("AI Crawlers Found in Your Logs")
        st.dataframe(df_counts)
        
