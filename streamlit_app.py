# is_ai_crawling_my_website.py

import streamlit as st
import pandas as pd
import requests
import json

# ----------------------------
# FONCTION POUR CHARGER LE JSON DES ROBOTS IA
# ----------------------------
@st.cache_data
def load_ai_robots(url):
    """
    Charge le fichier JSON contenant la liste des robots IA.
    Args:
        url (str): URL du fichier JSON.
    Returns:
        list: Liste de dictionnaires avec 'name' et 'user-agent'.
    """
    response = requests.get(url)
    if response.status_code == 200:
        robots = response.json()
        return robots
    else:
        st.error("Impossible de charger la liste des robots IA.")
        return []

# ----------------------------
# FONCTION POUR PARCOURIR LE FICHIER DE LOGS
# ----------------------------
def analyze_logs(log_file, ai_robots):
    """
    Analyse les logs ligne par ligne et compte les occurrences des robots IA.
    Args:
        log_file (UploadedFile): Fichier de logs fourni par l'utilisateur.
        ai_robots (list): Liste des robots IA avec 'name' et 'user-agent'.
    Returns:
        dict: Dictionnaire avec le nom du robot IA comme clé et le nombre d'occurrences comme valeur.
    """
    # Initialisation du compteur pour chaque robot
    counts = {robot['name']: 0 for robot in ai_robots}

    # Lecture ligne par ligne du fichier
    for line in log_file:
        # Conversion en string si nécessaire
        line_str = line.decode('utf-8', errors='ignore')
        # Vérification pour chaque robot
        for robot in ai_robots:
            if robot['user-agent'] in line_str:
                counts[robot['name']] += 1
    return counts

# ----------------------------
# INTERFACE STREAMLIT
# ----------------------------
# Titre principal de l'application
st.title("Is AI crawling my website?")

# Description de l'application
st.markdown("""
This application helps you detect AI crawlers in your website logs.  
Upload your log file (max 50 MB), and it will search for known AI bots.
""")

# URL du JSON contenant les robots IA
JSON_URL = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.json"

# Chargement des robots IA
ai_robots = load_ai_robots(JSON_URL)

# Upload du fichier de logs
uploaded_file = st.file_uploader(
    "Upload your log file (max 50 MB, uncompressed)", 
    type=None  # Autorise tous les types de fichiers
)

# Analyse du fichier après upload
if uploaded_file is not None:
    if uploaded_file.size > 50 * 1024 * 1024:
        st.error("File too large! Please upload a file smaller than 50 MB.")
    else:
        with st.spinner("Analyzing logs..."):
            counts = analyze_logs(uploaded_file, ai_robots)
        
        # Création d'un DataFrame pour un rendu clair
        df_results = pd.DataFrame(list(counts.items()), columns=["AI Robot Name", "Occurrences"])
        #df_results = df_results[df_results["Occurrences"] > 0]  # Filtrer les robots non détectés
        df_results = df_results.sort_values(by="Occurrences", ascending=False)

        if df_results.empty:
            st.success("No AI crawlers detected in your logs!")
        else:
            st.subheader("Detected AI Crawlers")
            st.table(df_results)
