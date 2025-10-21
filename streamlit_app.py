import streamlit as st
import pandas as pd
import requests
import json

# ------------------------------
# Page configuration
# ------------------------------
st.set_page_config(
    page_title="Is AI Crawling My Website?",
    page_icon="🤖",
    layout="centered"
)

# ------------------------------
# Titre et description
# ------------------------------
st.title("Is AI Crawling My Website?")
st.write("""
This application checks if your website logs contain requests from AI crawlers.  
Upload your log file, and it will search for known AI bots in it.
""")

# ------------------------------
# Upload du fichier de log
# ------------------------------
uploaded_file = st.file_uploader(
    "Upload your log file (max 50MB, uncompressed)",
    type=None,
    accept_multiple_files=False
)

if uploaded_file is not None:
    if uploaded_file.size > 50 * 1024 * 1024:
        st.error("The file is too large. Please upload a file smaller than 50MB.")
    else:
        # ------------------------------
        # Lecture du fichier JSON des robots IA
        # ------------------------------
        json_url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.json"
        response = requests.get(json_url)
        if response.status_code != 200:
            st.error("Failed to load AI bots JSON database.")
        else:
            robots_ia = response.json()  # Liste de dictionnaires avec "name" et "user-agent"

            # ------------------------------
            # Initialisation du compteur
            # ------------------------------
            results = {robot['name']: 0 for robot in robots_ia}

            # ------------------------------
            # Parcours du fichier de log ligne par ligne
            # ------------------------------
            st.info("Processing the log file... This may take a while for large files.")
            
            # On décode en UTF-8, on ignore les erreurs d'encodage
            for line_bytes in uploaded_file:
                try:
                    line = line_bytes.decode('utf-8', errors='ignore')
                except Exception:
                    continue
                
                # On cherche chaque user-agent connu dans la ligne
                for robot in robots_ia:
                    if robot['user-agent'] in line:
                        results[robot['name']] += 1

            # ------------------------------
            # Affichage des résultats
            # ------------------------------
            st.subheader("Detected AI Crawlers")
            df_results = pd.DataFrame(list(results.items()), columns=["AI Crawler Name", "Occurrences"])
            df_results = df_results[df_results["Occurrences"] > 0].sort_values(by="Occurrences", ascending=False)
            
            if df_results.empty:
                st.success("No AI crawlers detected in your logs.")
            else:
                st.table(df_results)
