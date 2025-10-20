import streamlit as st
import pandas as pd
import re
from io import StringIO
import requests

st.set_page_config(page_title="Is AI Crawling My Website?", layout="wide")
st.title("Is AI Crawling My Website? 🤖")

# --- Upload du fichier de logs ---
uploaded_file = st.file_uploader(
    "Upload your log file (max 5MB, non-compressed)",
    type=["txt", "log", "csv"]
)

# --- Charger le fichier de référence des crawlers ---
ROBOTS_URL = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/e21bed70c4b9cdf9013f9c17da6490c95395f6c6/robots-ia.txt"
robots_df = pd.read_csv(ROBOTS_URL, sep="\t", header=0, names=["name_bot","user_agent","ip"])

# --- Définir les groupes d'IA pour le rapport ---
IA_GROUPS = {
    "Open AI": ["ChatGPT Search Bot", "ChatGPT-User", "ChatGPT-GPTBot"],
    "Perplexity": ["Perplexity-Bot", "Perplexity‑User"],
    "Google": ["Google-Gemini"],
    "Mistral": ["MistralAI-User"]
}

# --- Fonction pour extraire le status code ---
def extract_status_code(line):
    """
    Extrait le code HTTP d'une ligne de log Apache/Nginx.
    Capture uniquement le nombre à 3 chiffres juste après la requête entre guillemets.
    """
    # Cherche le code après la requête HTTP "GET ... HTTP/1.1"
    m = re.search(r'"\s*(?:GET|POST|HEAD|PUT|DELETE|OPTIONS|PATCH) [^"]+ HTTP/[\d.]+"\s+(\d{3})', line, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None

# --- Fonction pour analyser les logs ---
def analyze_logs(log_lines, robots_df):
    hits = []
    summary = {bot: [] for bot in robots_df["name_bot"]}
    
    for line in log_lines:
        line_lower = line.lower()
        for _, bot in robots_df.iterrows():
            user_agent = str(bot["user_agent"]).lower()
            ip = str(bot["ip"]).lower()
            if user_agent in line_lower and ip in line_lower:
                status_code = extract_status_code(line)
                if status_code is not None:
                    summary[bot["name_bot"]].append(status_code)
                    hits.append((bot["name_bot"], line.strip(), status_code))
    return hits, summary

# --- Génération du rapport ---
def generate_report(summary):
    report = ""
    for ia_name, bots in IA_GROUPS.items():
        report += f"### Is {ia_name} crawling my website?\n"
        for bot in bots:
            codes = summary.get(bot, [])
            if not codes:
                status = f"No hit detected by {bot}"
            else:
                if all(c in range(200, 401) for c in codes):
                    status = "yes"
                else:
                    status = "no"
            report += f"- {bot} : {status}\n"
        report += "\n"
    return report

# --- Affichage principal ---
if uploaded_file:
    if uploaded_file.size > 5*1024*1024:
        st.error("File exceeds 5 MB limit")
    else:
        content = StringIO(uploaded_file.getvalue().decode("utf-8"))
        log_lines = content.readlines()
        
        hits, summary = analyze_logs(log_lines, robots_df)
        
        # Rapport texte
        report = generate_report(summary)
        st.markdown(report)
        
        # Tableau récap
        recap_data = []
        for bot, codes in summary.items():
            counts = {}
            for code in codes:
                counts[code] = counts.get(code, 0) + 1
            recap_data.append({
                "name_bot": bot,
                "status_code_counts": counts
            })
        st.subheader("Summary Table")
        st.dataframe(pd.DataFrame(recap_data))
        
        # Téléchargement des lignes filtrées
        if hits:
            filtered_lines = "\n".join([line for _, line, _ in hits])
            st.download_button(
                label="Download filtered logs",
                data=filtered_lines,
                file_name="filtered_logs.txt",
                mime="text/plain"
            )
