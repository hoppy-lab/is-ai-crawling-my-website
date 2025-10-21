import streamlit as st
import pandas as pd

# -------------------------------------------------------------
# Titre et description de l'application
# -------------------------------------------------------------
st.set_page_config(page_title="Is AI Crawling My Website?", page_icon="🤖", layout="centered")
st.title("Is AI Crawling My Website?")
st.write("This application detects the presence of AI bots in your website logs by analyzing User-Agent strings.")

# -------------------------------------------------------------
# Téléchargement du fichier de logs
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
    Charge le fichier CSV depuis GitHub.
    Le séparateur est une tabulation, les chaînes entre guillemets sont conservées correctement.
    """
    df = pd.read_csv(
        url,
        sep="\t",        # Tabulation
        header=None,     # Pas d'en-tête dans le CSV
        names=["name", "user_agent", "ip_start"],  # Nom des colonnes
        quotechar='"'    # Gère les guillemets autour du User-Agent
    )
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
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="ignore")
        # Vérification de chaque User-Agent complet
        for idx, row in robots_df.iterrows():
            if row["user_agent"] in line:  # Utilisation du User-Agent complet
                bot_counts[row["name"]] += 1
    
    # Affichage des résultats
    st.subheader("AI crawler occurrences in your log file")
    results_df = pd.DataFrame(list(bot_counts.items()), columns=["AI Crawler", "Occurrences"])
    st.dataframe(results_df.sort_values(by="Occurrences", ascending=False))
    st.success("Analysis complete!")
