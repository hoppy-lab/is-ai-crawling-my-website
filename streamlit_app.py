import streamlit as st
import pandas as pd
import requests

# -------------------------------------------------------------
# Titre et description de l'application
# -------------------------------------------------------------
st.set_page_config(page_title="Is AI Crawling My Website?", page_icon="🤖", layout="centered")

st.title("Is AI Crawling My Website?")
st.write("This application detects the presence of AI bots in your website logs by analyzing User-Agent strings.")

# -------------------------------------------------------------
# Téléchargement du fichier de logs par l'utilisateur
# -------------------------------------------------------------
uploaded_file = st.file_uploader(
    "Upload your log file (less than 50 MB, any text format, uncompressed)",
    type=["log", "txt", "csv", "tsv"],
)

# -------------------------------------------------------------
# Chargement du fichier de référence contenant les robots IA
# -------------------------------------------------------------
robots_url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.csv"

@st.cache_data
def load_robots(url):
    """
    Cette fonction charge le fichier CSV contenant les robots IA depuis GitHub.
    Il n'a pas d'en-tête, séparateur tabulation.
    Retourne un DataFrame pandas avec trois colonnes : name, user_agent_fragment, ip_start
    """
    df = pd.read_csv(url, sep="\t", header=None, names=["name", "user_agent_fragment", "ip_start"])
    return df

robots_df = load_robots(robots_url)

# Affichage des robots connus
st.subheader("Known AI crawlers")
st.dataframe(robots_df)

# -------------------------------------------------------------
# Analyse du fichier de logs uploadé
# -------------------------------------------------------------
if uploaded_file is not None:
    st.info("Analyzing your log file... this may take a few seconds for large files.")
    
    # Initialisation d'un dictionnaire pour compter les occurrences
    bot_counts = {name: 0 for name in robots_df["name"]}
    
    # Lecture ligne par ligne du fichier de logs
    for line in uploaded_file:
        # Convertir en string si c'est en bytes
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="ignore")
        # Vérifier chaque robot IA
        for idx, row in robots_df.iterrows():
            if row["user_agent_fragment"] in line:
                bot_counts[row["name"]] += 1
    
    # -------------------------------------------------------------
    # Affichage des résultats
    # -------------------------------------------------------------
    st.subheader("AI crawler occurrences in your log file")
    
    results_df = pd.DataFrame(list(bot_counts.items()), columns=["AI Crawler", "Occurrences"])
    st.dataframe(results_df.sort_values(by="Occurrences", ascending=False))
    
    st.success("Analysis complete!")
