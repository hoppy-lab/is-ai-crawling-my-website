import streamlit as st
import pandas as pd
import io
import re
import requests

st.set_page_config(page_title="Is AI crawling my website?", layout="wide")

st.title("Is AI crawling my website? 🤖")

# ------------------------
# Chargement du fichier de référence des bots
# ------------------------
CSV_URL = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.csv"

@st.cache_data
def load_reference():
    df = pd.read_csv(CSV_URL)
    # On renomme pour plus de clarté
    df.columns = ["name_bot", "user_agent", "ip"]
    return df

bots_df = load_reference()

# ------------------------
# Upload fichier de logs
# ------------------------
st.header("Upload your log file")
uploaded_file = st.file_uploader(
    "Choose a log file (plain text, max 5MB)",
    type=["txt", "log", "csv"]
)

if uploaded_file is not None:
    if uploaded_file.size > 5 * 1024 * 1024:
        st.error("File is too large (max 5MB).")
    else:
        # Lecture du contenu
        raw_content = uploaded_file.read().decode("utf-8", errors="ignore")
        st.success(f"File uploaded: {uploaded_file.name}, size: {uploaded_file.size} bytes")
        
        # ------------------------
        # Détection du séparateur
        # ------------------------
        sample_lines = raw_content.splitlines()[:10]
        possible_separators = [",", ";", "\t", "|", " "]
        sep_scores = {}
        for sep in possible_separators:
            counts = [len(line.split(sep)) for line in sample_lines]
            sep_scores[sep] = max(counts) - min(counts)
        # On choisit celui avec le moins de variance et au moins 2 colonnes
        separator = min([k for k, v in sep_scores.items() if v < 3], key=lambda x: sep_scores[x], default=" ")
        st.info(f"Detected separator: '{separator}'")

        # ------------------------
        # Lecture dataframe logs
        # ------------------------
        logs_df = pd.read_csv(io.StringIO(raw_content), sep=separator, header=None, dtype=str, engine="python")
        
        # Création d'une colonne avec la ligne complète
        logs_df['full_line'] = logs_df.astype(str).agg(separator.join, axis=1)
        
        # ------------------------
        # Extraction du status code
        # ------------------------
        # On cherche toute série de 3 chiffres entre 200 et 599 dans la ligne
        def extract_status(line):
            match = re.findall(r"\b([2-5][0-9]{2})\b", line)
            return match[0] if match else None

        logs_df['status_code'] = logs_df['full_line'].apply(extract_status)
        
        # ------------------------
        # Analyse des bots
        # ------------------------
        st.header("AI crawling analysis")
        
        report = {}
        selected_lines = pd.DataFrame(columns=logs_df.columns)
        
        for _, bot in bots_df.iterrows():
            name = bot["name_bot"]
            ua = bot["user_agent"].lower()
            ip = str(bot["ip"]).lower()
            
            # Lignes correspondant au bot
            bot_hits = logs_df[logs_df['full_line'].str.lower().str.contains(ua) & logs_df['full_line'].str.lower().str.contains(ip)]
            
            if bot_hits.empty:
                status = f"No hit detected by {name}"
            else:
                # Check status codes
                valid_hits = bot_hits[bot_hits['status_code'].astype(float).between(200, 499)]
                if valid_hits.empty:
                    status = "no"
                else:
                    status = "yes"
                    selected_lines = pd.concat([selected_lines, bot_hits])
            
            report[name] = {
                "status": status,
                "hits": bot_hits
            }
        
        # ------------------------
        # Affichage par catégorie
        # ------------------------
        categories = {
            "Open AI": ["ChatGPT Search Bot", "ChatGPT-User", "ChatGPT-GPTBot"],
            "Perplexity": ["Perplexity-Bot", "Perplexity-User"],
            "Google": ["Google-Gemini"],
            "Mistral": ["MistralAI-User"]
        }
        
        for cat, bots in categories.items():
            st.subheader(f"Is {cat} crawling my website?")
            for b in bots:
                if b in report:
                    st.write(f"- {b} : {report[b]['status']}")
                else:
                    st.write(f"- {b} : Not found in reference file")
        
        # ------------------------
        # Tableau récapitulatif
        # ------------------------
        st.header("Summary table per bot and status code")
        summary_data = []
        for name, info in report.items():
            hits = info["hits"]
            if hits.empty:
                summary_data.append({"name_bot": name, "status_code": "No hit", "count": 0})
            else:
                counts = hits['status_code'].value_counts()
                for code, c in counts.items():
                    summary_data.append({"name_bot": name, "status_code": code, "count": c})
        
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df)
        
        # ------------------------
        # Téléchargement du fichier filtré
        # ------------------------
        if not selected_lines.empty:
            csv_filtered = selected_lines.to_csv(index=False, sep=separator)
            st.download_button(
                label="Download filtered log lines",
                data=csv_filtered,
                file_name="filtered_logs.csv",
                mime="text/csv"
            )
