# Import des librairies nécessaires
import streamlit as st
import pandas as pd
import requests
from io import StringIO

# --- Écran d'accueil ---
st.title("Is AI crawling my website?")
st.write(
    """
    This application allows you to detect the presence of AI crawlers in your website logs. 
    Upload a CSV log file and the app will check if known AI bots are crawling your site.
    """
)

# --- Upload du fichier de logs ---
uploaded_file = st.file_uploader(
    "Upload your log file (CSV, max 50 MB)", 
    type="csv"
)

if uploaded_file is not None:
    # Vérifier la taille du fichier
    if uploaded_file.size > 50 * 1024 * 1024:
        st.error("The file is too large. Please upload a file smaller than 50 MB.")
    else:
        # Lecture du fichier CSV utilisateur
        # On lit ligne par ligne pour ne pas surcharger la mémoire
        file_content = StringIO(uploaded_file.getvalue().decode("utf-8"))
        log_lines = file_content.readlines()
        
        st.success(f"File loaded successfully! Total lines: {len(log_lines)}")

        # --- Chargement du fichier de référence robots-ia.csv ---
        robots_url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.csv"
        response = requests.get(robots_url)
        if response.status_code == 200:
            robots_data = pd.read_csv(
                StringIO(response.text), 
                sep=";", 
                header=None,  # pas d'en-tête
                names=["name", "user_agent_fragment", "ip_prefix"]
            )
            st.write("List of AI crawlers known:")
            st.dataframe(robots_data["name"])  # Affiche seulement les noms pour l’instant

            # --- Comptage des User-Agent dans le fichier log ---
            st.write("Counting occurrences of each AI crawler in your logs...")
            
            # Dictionnaire pour stocker les résultats
            crawler_counts = {}

            # Parcours de chaque robot
            for index, row in robots_data.iterrows():
                crawler_name = row["name"]
                user_agent_fragment = str(row["user_agent_fragment"])
                count = 0

                # Parcours des lignes de log
                for line in log_lines:
                    if user_agent_fragment in line:
                        count += 1
                
                crawler_counts[crawler_name] = count
            
            # --- Affichage des résultats ---
            result_df = pd.DataFrame(list(crawler_counts.items()), columns=["AI Crawler", "Occurrences"])
            st.write("Number of occurrences of each AI crawler in your log file:")
            st.dataframe(result_df)
        else:
            st.error("Failed to fetch AI crawlers reference file.")
