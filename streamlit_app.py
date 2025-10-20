import streamlit as st
import pandas as pd
import re
from io import StringIO, BytesIO
import requests

st.set_page_config(page_title="Is AI Crawling My Website?", layout="wide")
st.title("Is AI Crawling My Website? 🤖")

# --- Téléchargement du fichier de logs ---
uploaded_file = st.file_uploader(
    "Upload your log file (max 5MB, non-compressed)",
    type=["txt", "log", "csv"]
)

# --- Fonction pour détecter le séparateur ---
def detect_separator(sample):
    for sep in [",", ";", "\t", "|"]:
        if len(sample.split(sep)) > 1:
            return sep
    return None

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
def extract_status_code(line, sep):
    parts = line.split(sep)
    for part in parts:
        if re.match(r"^[2-5][0-9]{2}$", part):
            return int(part)
    return None

# --- Fonction pour analyser les logs ---
def analyze_logs(log_lines, robots_df, sep):
    hits = []
    summary = {bot: [] for bot in robots_df["name_bot"]}
    
    for line in log_lines:
        line_lower = line.lower()
        for _, bot in robots_df.iterrows():
            user_agent = bot["user_agent"].lower()
            ip = str(bot["ip"]).lower()
            if user_agent in line_lower and ip in line_lower:
                status_code = extract_status_code(line, sep)
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
        sample_line = content.readline()
        sep = detect_separator(sample_line)
        if not sep:
            st.error("Unable to detect separator automatically")
        else:
            st.success(f"Detected separator: '{sep}'")
            content.seek(0)
            log_lines = content.readlines()
            
            hits, summary = analyze_logs(log_lines, robots_df, sep)
            
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
