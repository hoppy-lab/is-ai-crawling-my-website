import streamlit as st
import pandas as pd
import re
import io
import requests

st.set_page_config(page_title="Is AI crawling my website ?", layout="wide")

st.title("🕵️ Is AI crawling my website ?")

# --- Charger le fichier de référence robots-ia.txt depuis GitHub ---
@st.cache_data
def load_reference():
    url = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/e21bed70c4b9cdf9013f9c17da6490c95395f6c6/robots-ia.txt"
    df_ref = pd.read_csv(url, sep="\t")  # fichier séparé par tabulation
    return df_ref

df_ref = load_reference()

# --- Upload du fichier ---
uploaded_file = st.file_uploader("📂 Upload your log file", type=["log", "txt", "csv"], accept_multiple_files=False)

if uploaded_file:
    if uploaded_file.size > 5_000_000:
        st.error("❌ File too large (max 5 MB)")
    else:
        # --- Détection séparateur ---
        sample = uploaded_file.read(2048).decode(errors="ignore")
        uploaded_file.seek(0)
        possible_seps = [",", ";", "\t", "|", " "]
        sep_counts = {sep: sample.count(sep) for sep in possible_seps}
        separator = max(sep_counts, key=sep_counts.get)

        if separator == ".":
            st.error("❌ Invalid separator (.) not allowed")
        else:
            st.info(f"✅ Detected separator: `{separator}`")

            # Lire le fichier complet
            logs = uploaded_file.read().decode(errors="ignore").splitlines()

            selected_lines = []
            results = {bot: {"hits": [], "status": []} for bot in df_ref["name_bot"]}

            # Regex pour le status code
            status_pattern = re.compile(rf"{separator}([2-5][0-9]{{2}}){separator}")

            for line in logs:
                for _, row in df_ref.iterrows():
                    bot_name = row["name_bot"]
                    ua = row["user-agent"]
                    ip = row["ip"]

                    if ua in line and ip in line:
                        # Extraire status code
                        m = status_pattern.search(line)
                        if m:
                            status = int(m.group(1))
                            results[bot_name]["hits"].append(line)
                            results[bot_name]["status"].append(status)
                            selected_lines.append(line)

            # --- Analyse des résultats ---
            def is_yes(status_list):
                if not status_list:
                    return "No hit detected"
                if all(200 <= s < 500 for s in status_list):
                    return "yes"
                return "no"

            # --- Affichage ---
            st.subheader("🔎 Analysis by AI provider")

            providers = {
                "Is Open AI crawling my website ?": ["ChatGPT Search Bot", "ChatGPT-User", "ChatGPT-GPTBot"],
                "Is Perplexity crawling my website ?": ["Perplexity-Bot", "Perplexity-User"],
                "Is Google crawling my website ?": ["Google-Gemini"],
                "Is Mistral crawling my website ?": ["MistralAI-User"]
            }

            for provider, bots in providers.items():
                st.markdown(f"### {provider}")
                for bot in bots:
                    verdict = is_yes(results[bot]["status"])
                    if verdict == "No hit detected":
                        st.write(f"- {bot} : No hit detected by {bot}")
                    else:
                        st.write(f"- {bot} : {verdict}")

            # --- Tableau récap ---
            st.subheader("📊 Recap Table")
            recap = []
            for bot, data in results.items():
                status_counts = pd.Series(data["status"]).value_counts().to_dict()
                recap.append({"name_bot": bot, **status_counts})
            df_recap = pd.DataFrame(recap).fillna(0).astype(int)
            st.dataframe(df_recap)

            # --- Téléchargement des lignes sélectionnées ---
            if selected_lines:
                output = "\n".join(selected_lines)
                st.download_button(
                    "⬇️ Download selected lines",
                    data=output,
                    file_name="ai_crawlers_logs.txt",
                    mime="text/plain"
                )
