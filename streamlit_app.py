import streamlit as st
import pandas as pd
import re
import io
from typing import List

st.set_page_config(page_title="Is AI crawling my website ?", layout="wide")
st.title("🕵️ Is AI crawling my website ?")

# --- Charger le fichier de référence robots-ia.txt depuis GitHub (raw) ---
@st.cache_data
def load_reference():
    url = ("https://raw.githubusercontent.com/"
           "hoppy-lab/is-ai-crawling-my-website/"
           "e21bed70c4b9cdf9013f9c17da6490c95395f6c6/robots-ia.txt")
    # le fichier est tabulé ; on normalise les colonnes (strip, lower)
    df_ref = pd.read_csv(url, sep="\t", dtype=str).fillna("")
    df_ref["name_bot_raw"] = df_ref["name_bot"]
    df_ref["name_bot"] = df_ref["name_bot"].astype(str).str.strip()
    df_ref["ua"] = df_ref["user-agent"].astype(str).str.strip()
    df_ref["ip"] = df_ref["ip"].astype(str).str.strip()
    return df_ref

df_ref = load_reference()

st.markdown("Upload a log file (plain text, not compressed, max 5 MB).")

uploaded_file = st.file_uploader("📂 Upload your log file", type=["log", "txt", "csv"], accept_multiple_files=False)

def detect_separator(sample: str, candidates: List[str] = [",", ";", "\t", "|", " "]):
    counts = {sep: sample.count(sep) for sep in candidates}
    # choisir le plus fréquent ; si tous nuls, fallback à espace
    separator = max(counts, key=counts.get)
    return separator

def extract_status_from_line(line: str, sep: str):
    # échappe le séparateur pour regex
    sep_esc = re.escape(sep)
    # chercher un code de 3 chiffres 200-599 entouré par séparateurs ou bord de ligne
    pattern = re.compile(rf"(?:^|{sep_esc})([2-5][0-9]{{2}})(?:{sep_esc}|$)")
    m = pattern.search(line)
    if m:
        try:
            return int(m.group(1))
        except:
            return None
    return None

if uploaded_file:
    if uploaded_file.size > 5_000_000:
        st.error("❌ Fichier trop volumineux (max 5 MB).")
    else:
        # lire un échantillon pour détecter le séparateur
        raw = uploaded_file.read()
        try:
            sample = raw[:4096].decode(errors="ignore")
        except:
            sample = str(raw[:4096])
        # repositionner le buffer pour lecture complète
        uploaded_file.seek(0)

        separator = detect_separator(sample)
        if separator == ".":
            st.error("❌ Le séparateur détecté est '.' — interdit selon le cahier des charges.")
        else:
            st.success(f"✅ Séparateur détecté : `{separator}`")
            # lire toutes les lignes (ne pas tenter de parser en colonnes)
            content = uploaded_file.read().decode(errors="ignore")
            lines = content.splitlines()

            # Normaliser les clefs de référence
            # results : clé = name_bot original (non modifié pour affichage), valeur = dict
            results = {}
            # build mapping using normalized name as key to allow robust matching with provider list
            for _, row in df_ref.iterrows():
                bot_name = row["name_bot"]  # déjà strip'
                results[bot_name] = {"hits": [], "status": [], "ua": row["ua"], "ip": row["ip"], "display_name": row["name_bot_raw"]}

            selected_lines = []

            # scanner les lignes
            for line in lines:
                # pour chaque robot de référence, vérifier présence UA & IP (telle que demandée)
                for bot_name, info in results.items():
                    # require both UA substring and IP substring to be present in the same line
                    if info["ua"] and info["ua"] in line and info["ip"] and info["ip"] in line:
                        status = extract_status_from_line(line, separator)
                        # stocker même si status est None (pour compter "hits" sans status)
                        results[bot_name]["hits"].append(line)
                        if status is not None:
                            results[bot_name]["status"].append(status)
                        else:
                            results[bot_name]["status"].append(None)
                        selected_lines.append(line)

            # fonction de décision yes/no
            def decide_status(status_list: List[int]):
                # status_list peut contenir None
                if not status_list:
                    return "No hit detected"
                # si au moins un None -> considérer comme non fiable -> 'no'
                cleaned = [s for s in status_list if s is not None]
                if len(cleaned) == 0 and any(s is None for s in status_list):
                    # hits trouvés mais aucun status parseable
                    return "no"
                # si un status >=500 -> no
                if any(s is not None and s >= 500 for s in status_list):
                    return "no"
                # si tous parseables sont 200-499 -> yes
                if all((s is not None and 200 <= s < 500) for s in status_list):
                    return "yes"
                # sinon (ex : mixte incluant None), dire no
                return "no"

            # Présentation par fournisseurs demandés (hardcodé)
            providers = {
                "Is Open AI crawling my website ?": ["ChatGPT Search Bot", "ChatGPT-User", "ChatGPT-GPTBot"],
                "Is Perplexity crawling my website ?": ["Perplexity-Bot", "Perplexity-User"],
                "Is Google crawling my website ?": ["Google-Gemini"],
                "Is Mistral crawling my website ?": ["MistralAI-User"]
            }

            st.subheader("🔎 Analysis by AI provider")

            # Affichage détaillé : un paragraphe par IA (fournisseur)
            for provider_title, bots in providers.items():
                st.markdown(f"### {provider_title}")
                for bot in bots:
                    # attempt get matching bot key (exact match on name_bot)
                    bot_key = None
                    # recherche insensible si exact key not found
                    if bot in results:
                        bot_key = bot
                    else:
                        # fallback : matching case-insensitive or substring in name
                        for k in results.keys():
                            if k.lower() == bot.lower() or bot.lower() in k.lower() or k.lower() in bot.lower():
                                bot_key = k
                                break

                    if bot_key is None:
                        st.write(f"- {bot} : No hit detected by {bot} (bot not present in reference file).")
                        continue

                    status_list = results.get(bot_key, {}).get("status", [])
                    verdict = decide_status(status_list)
                    if verdict == "No hit detected":
                        st.write(f"- {bot} : No hit detected by {bot}")
                    else:
                        st.write(f"- {bot} : {verdict}")

            # Tableau récapitulatif : chaque robot (name_bot) et count par status code
            st.subheader("📊 Recap table (counts per status code)")
            rows = []
            for bot_name, info in results.items():
                # compter status codes (None regroupé sous "unknown")
                status_series = pd.Series(info["status"])
                counts = status_series.value_counts(dropna=False).to_dict()
                # map None to "unknown"
                row = {"name_bot": bot_name}
                for k, v in counts.items():
                    if pd.isna(k):
                        row["unknown"] = v
                    else:
                        row[str(int(k))] = v
                rows.append(row)
            if rows:
                df_recap = pd.DataFrame(rows).fillna(0).astype(int)
                st.dataframe(df_recap)
            else:
                st.info("Aucun bot listé dans le fichier de référence n'a été comparé.")

            # Téléchargement des lignes sélectionnées
            if selected_lines:
                out_text = "\n".join(selected_lines)
                st.download_button(
                    "⬇️ Télécharger les lignes sélectionnées",
                    data=out_text.encode("utf-8"),
                    file_name="ai_crawlers_selected_lines.txt",
                    mime="text/plain"
                )
            else:
                st.info("Aucune ligne sélectionnée par le programme (no hits).")
