# Import des librairies nécessaires
import streamlit as st
import pandas as pd
import requests
from io import StringIO

# --- Écran d'accueil ---
st.title("Is AI crawling my website?")  # Titre de l'application
st.write(
    """
    Detect the presence of AI bots in your website logs. 
    Upload a log file (any text format, not compressed) and the app will check for known AI crawlers.
    
    The detection counts only lines where both the User-Agent fragment **and** the IP prefix match.
    """
)

# --- Upload du fichier de logs ---
uploaded_file = st.file_uploader(
    "Upload your log file (max 50 MB, any text format)", 
    type=None  # n'importe quel type sauf compressé
)

if uploaded_file is not None:
    # Vérification de la taille du fichier
    if uploaded_file.size > 50 * 1024 * 1024:  # 50 MB en octets
        st.error("The file is too large. Please upload a file smaller than 50 MB.")
    else:
        # Lecture du fichier ligne par ligne
        file_content = StringIO(uploaded_file.getvalue().decode("utf-8", errors="ignore"))
        log_lines = file_content.readlines()
        st.success(f"File loaded successfully! Total lines: {len(log_lines)}")

        # --- Chargement du fichier de référence robots-ia.csv depuis GitHub ---
        robots_url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.csv"
        response = requests.get(robots_url)
        if response.status_code == 200:
            # Lecture du CSV de référence avec pandas
            robots_data = pd.read_csv(
                StringIO(response.text), 
                sep=";", 
                header=None,  # pas d'en-tête
                names=["name", "user_agent_fragment", "ip_prefix"]
            )

            st.write("List of AI crawlers known:")
            st.dataframe(robots_data["name"])  # Affiche uniquement les noms des robots

            # --- Comptage des occurrences selon User-Agent ET IP ---
            st.write("Counting occurrences of each AI crawler in your logs (User-Agent AND IP must match)...")

            crawler_counts = {}  # Dictionnaire pour stocker les résultats

            # Pour chaque robot dans le fichier de référence
            for index, row in robots_data.iterrows():
                crawler_name = row["name"]  # Nom du robot IA
                user_agent_fragment = str(row["user_agent_fragment"])  # Fragment du User-Agent
                ip_prefix = str(row["ip_prefix"])  # Début de l'IP
                count = 0  # Initialisation du compteur

                # Parcours de chaque ligne de log
                for line in log_lines:
                    # Vérifie si la ligne contient à la fois le User-Agent et l'IP
                    if user_agent_fragment in line and ip_prefix in line:
                        count += 1
                
                crawler_counts[crawler_name] = count  # Enregistrement du résultat

            # --- Affichage des résultats dans un tableau ---
            result_df = pd.DataFrame(
                list(crawler_counts.items()), 
                columns=["AI Crawler", "Occurrences"]
            )
            st.write("Number of occurrences of each AI crawler in your log file:")
            st.dataframe(result_df)

        else:
            st.error("Failed to fetch AI crawlers reference file from GitHub.")
