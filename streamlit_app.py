import streamlit as st
import pandas as pd
import requests
import io

# --- Titre et description de l'application ---
st.title("is AI crawlin my ebsitewebsite")
st.write("This application detects the presence of AI bots in your website logs.")

# --- Interface de chargement du fichier de logs ---
# L'utilisateur peut uploader un fichier de moins de 50 Mo, non compressé
uploaded_file = st.file_uploader(
    "Upload your log file (max 50MB, any format except compressed)", type=None
)

# --- Si un fichier est uploadé ---
if uploaded_file:
    # URL du fichier de référence contenant les infos sur les crawlers IA
    url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.txt"
    response = requests.get(url)

    # Vérifie que le fichier a bien été récupéré
    if response.status_code == 200:
        # Lecture du fichier de référence dans un DataFrame pandas
        reference_data = pd.read_csv(io.StringIO(response.text), sep='\t', header=None)
        reference_data.columns = ['Crawler Name', 'User-Agent Fragment', 'IP Prefix']

        # Initialisation d'un dictionnaire pour compter les occurrences
        crawler_counts = {name: 0 for name in reference_data['Crawler Name']}

        # Lecture du fichier de logs ligne par ligne
        for line in uploaded_file:
            decoded_line = line.decode('utf-8', errors='ignore')  # Décodage en UTF-8
            for index, row in reference_data.iterrows():
                # Si le fragment de User-Agent est trouvé dans la ligne
                if row['User-Agent Fragment'] in decoded_line:
                    crawler_counts[row['Crawler Name']] += 1

        # --- Affichage des résultats ---
        st.subheader("Detected AI Crawlers")
        for crawler, count in crawler_counts.items():
            st.write(f"{crawler}: {count} occurrences")
    else:
        st.error("Failed to load reference data from GitHub.")
