import streamlit as st
import pandas as pd
import io
import re
from collections import defaultdict

# --- FONCTIONS UTILITAIRES ---
def detect_separator(sample_line):
    """Détecte automatiquement le séparateur de colonnes (autre que '.')"""
    for sep in [',', ';', '\t', '|']:
        if sep in sample_line:
            return sep
    return None

def extract_status_code(line, separator):
    """Extrait le status code à partir d'une ligne de log"""
    parts = line.strip().split(separator)
    for part in parts:
        if re.fullmatch(r'[2-5]\d{2}', part):
            return int(part)
    return None

def check_crawler_hit(line, crawler):
    """Vérifie si la ligne correspond au crawler (user-agent et IP)"""
    return crawler['user-agent'] in line and crawler['ip'] in line

# --- STREAMLIT INTERFACE ---
st.title("Is AI crawling my website ?")
st.write("Upload your log file (max 5MB, non compressed).")

log_file = st.file_uploader("Upload log file", type=['txt', 'log', 'csv'])
ref_url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/e21bed70c4b9cdf9013f9c17da6490c95395f6c6/robots-ia.txt"

if log_file is not None:
    if log_file.size > 5*1024*1024:
        st.error("File exceeds 5MB limit.")
    else:
        # --- Lecture fichier logs ---
        first_line = log_file.readline().decode("utf-8")
        separator = detect_separator(first_line)
        if separator is None:
            st.error("Could not detect separator.")
        else:
            log_file.seek(0)
            logs = log_file.read().decode("utf-8").splitlines()

            # --- Lecture fichier robots ---
            robots_df = pd.read_csv(ref_url)
            crawlers = robots_df.to_dict('records')

            # --- Analyse logs ---
            results = defaultdict(lambda: defaultdict(list))
            filtered_lines = []

            for line in logs:
                status_code = extract_status_code(line, separator)
                if status_code is None:
                    continue

                for crawler in crawlers:
                    if check_crawler_hit(line, crawler):
                        results[crawler['name_bot']][status_code].append(line)
                        filtered_lines.append(line)

            # --- Création rapport ---
            ia_groups = {
                "Open AI": ["ChatGPT Search Bot", "ChatGPT-User", "ChatGPT-GPTBot"],
                "Perplexity": ["Perplexity-Bot", "Perplexity-User"],
                "Google": ["Google-Gemini"],
                "Mistral": ["MistralAI-User"]
            }

            st.header("AI Crawling Report")
            for ia_name, bots in ia_groups.items():
                st.subheader(f"Is {ia_name} crawling my website ?")
                for bot in bots:
                    bot_hits = results.get(bot, {})
                    if not bot_hits:
                        st.write(f"- {bot}: No hit detected by {bot}")
                    else:
                        # Vérifie les status codes
                        all_ok = all(int(code)//100 in [2,3,4] for code in bot_hits.keys())
                        st.write(f"- {bot}: {'yes' if all_ok else 'no'}")

            # --- Tableau récap ---
            st.header("Summary Table")
            table_rows = []
            for bot, codes in results.items():
                code_counts = {str(code): len(lines) for code, lines in codes.items()}
                table_rows.append({"name_bot": bot, **code_counts})
            if table_rows:
                df_summary = pd.DataFrame(table_rows).fillna(0).astype(int)
                st.dataframe(df_summary)
            else:
                st.write("No AI crawler hits detected in the logs.")

            # --- Téléchargement des lignes filtrées ---
            if filtered_lines:
                filtered_text = "\n".join(filtered_lines)
                st.download_button(
                    "Download filtered logs",
                    data=filtered_text,
                    file_name="filtered_logs.txt",
                    mime="text/plain"
                )
