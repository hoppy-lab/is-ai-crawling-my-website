import streamlit as st
import pandas as pd
import re
from io import StringIO
import requests
from collections import defaultdict

st.title("Is AI crawling my website ?")
st.write("Upload your log file (max 5MB, non compressed).")

# --- Upload log file ---
log_file = st.file_uploader("Upload log file", type=['txt', 'log', 'csv'])

def detect_separator(line):
    for sep in [',', ';', '\t', '|']:
        if sep in line:
            return sep
    return None

def extract_status_code(line, sep):
    parts = line.strip().split(sep)
    for part in parts:
        if re.fullmatch(r'[2-5]\d{2}', part):
            return int(part)
    return None

def check_crawler_hit(line, crawler):
    """
    Vérifie si la ligne de log contient le crawler IA
    - user-agent (2ᵉ colonne) et ip (3ᵉ colonne) sont recherchés comme sous-chaînes
    - name_bot (1ʳᵉ colonne) sert uniquement pour l'affichage
    """
    ua = crawler['user-agent'].lower()
    ip = crawler['ip']
    line_clean = line.strip().lower()
    return ua in line_clean and ip in line_clean

if log_file is not None:
    if log_file.size > 5*1024*1024:
        st.error("File exceeds 5MB limit.")
    else:
        log_content = log_file.read().decode("utf-8").splitlines()
        if not log_content:
            st.error("Log file is empty.")
        else:
            sep = detect_separator(log_content[0])
            if sep is None:
                st.error("Could not detect separator in log file.")
            else:
                # --- Download and read robots-ia.txt ---
                robots_url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/e21bed70c4b9cdf9013f9c17da6490c95395f6c6/robots-ia.txt"
                response = requests.get(robots_url)
                if response.status_code != 200:
                    st.error("Failed to download robots-ia.txt")
                else:
                    content = response.text
                    robots_df = pd.read_csv(StringIO(content), sep="\t")

                    # --- Création liste de crawlers par index de colonnes ---
                    crawlers = []
                    for row in robots_df.itertuples(index=False):
                        crawlers.append({
                            "name_bot": str(row[0]).strip(),
                            "user-agent": str(row[1]).strip(),
                            "ip": str(row[2]).strip()
                        })

                    # --- Analyse logs ---
                    results = defaultdict(lambda: defaultdict(list))
                    filtered_lines = []

                    for line in log_content:
                        status_code = extract_status_code(line, sep)
                        if status_code is None:
                            continue
                        for crawler in crawlers:
                            if check_crawler_hit(line, crawler):
                                results[crawler['name_bot']][status_code].append(line)
                                filtered_lines.append(line)

                    # --- IA groups pour le rapport ---
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
                                all_ok = all(int(code)//100 in [2,3,4] for code in bot_hits.keys())
                                st.write(f"- {bot}: {'yes' if all_ok else 'no'}")

                    # --- Tableau récap détaillé ---
                    st.header("Detailed Summary Table")
                    all_codes = set()
                    for codes in results.values():
                        all_codes.update(codes.keys())
                    all_codes = sorted(all_codes)

                    table_rows = []
                    for crawler in crawlers:
                        bot_name = crawler['name_bot']
                        bot_hits = results.get(bot_name, {})
                        row = {"name_bot": bot_name}
                        for code in all_codes:
                            row[str(code)] = len(bot_hits.get(code, []))
                        table_rows.append(row)

                    # Conversion sécurisée en int
                    df_summary = pd.DataFrame(table_rows).fillna(0)
                    for col in df_summary.columns:
                        if col != "name_bot":
                            df_summary[col] = pd.to_numeric(df_summary[col], errors='coerce').fillna(0).astype(int)

                    st.dataframe(df_summary)

                    # --- Téléchargement lignes filtrées ---
                    if filtered_lines:
                        filtered_text = "\n".join(filtered_lines)
                        st.download_button(
                            "Download filtered logs",
                            data=filtered_text,
                            file_name="filtered_logs.txt",
                            mime="text/plain"
                        )
