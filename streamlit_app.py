import re
from io import StringIO

import pandas as pd
import requests
import streamlit as st

# --------------------------------------------------------------------
# Is AI crawling my website ? — application Streamlit
# - charge un échantillon de logs (CSV ou TXT)
# - détecte IP / User-Agent / Status-Code par heuristiques/regex
# - compare aux definitions de crawlers fournies dans robots-ia.txt (GitHub)
# --------------------------------------------------------------------

# Configuration page
st.set_page_config(page_title="Is AI crawling my website ?")
st.title("Is AI crawling my website ?")
st.markdown(
    """
- Importez un échantillon de vos logs (une journée par exemple) — max 5 Mo
- Aucun fichier compressé autorisé
- Le programme essaie d'extraire automatiquement : IP, User-Agent, Status-Code (regex)
- Fournissez l'URL brute GitHub du fichier `robots-ia.txt` (format `Nom;IP;User-Agent`) ou laissez l'URL par défaut
"""
)

# Inputs utilisateur
uploaded_file = st.file_uploader("Importez votre fichier de logs (CSV ou TXT, pas d'archive)", type=["csv", "txt"])
robots_url = st.text_input(
    "URL brute du fichier robots-ia.txt sur GitHub (raw)",
    "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/e21bed70c4b9cdf9013f9c17da6490c95395f6c6/robots-ia.txt",
)


# ------------------- Helpers / utilitaires -------------------
def to_raw_github(url: str) -> str:
    """Convertit une URL GitHub contenant /blob/ en URL raw.githubusercontent.com."""
    if not url:
        return url
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url


def is_compressed_name(name: str) -> bool:
    """Détecte certaines extensions d'archive pour les refuser."""
    name = (name or "").lower()
    return any(name.endswith(ext) for ext in (".zip", ".gz", ".bz2", ".xz", ".7z", ".tar"))


IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
STATUS_RE = re.compile(r"\b([1-5]\d{2})\b")


def extract_from_text_lines(text: str) -> pd.DataFrame:
    """
    Parse libre ligne par ligne pour extraire IP / Status-Code / User-Agent.
    - IP : premier match IPv4
    - Status : premier code 3 chiffres (100-599)
    - UA : dernière chaîne entre guillemets, sinon contexte autour d'un token connu
    """
    rows = []
    known_ua_tokens = [
        "mozilla", "curl", "bot", "spider", "bingbot", "googlebot", "gptbot", "chatgpt", "perplexity", "mistral"
    ]
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        ip_m = IP_RE.search(line)
        ip = ip_m.group() if ip_m else ""
        status_m = STATUS_RE.search(line)
        status = status_m.group() if status_m else ""
        quoted = re.findall(r'"([^"]{3,500})"', line)
        ua = quoted[-1].strip() if quoted else ""
        if not ua:
            low = line.lower()
            for token in known_ua_tokens:
                if token in low:
                    idx = low.find(token)
                    start = max(0, idx - 60)
                    end = min(len(line), idx + 160)
                    ua = line[start:end].strip()
                    break
        rows.append({"IP": ip, "User-Agent": ua, "Status-Code": status, "raw": line})
    return pd.DataFrame(rows)


def try_load_logs(uploaded) -> pd.DataFrame | None:
    """
    Lit le fichier uploadé :
    - refuse les archives et fichiers > 5 Mo
    - tente pd.read_csv avec ';' puis ','
    - en fallback, parse le texte avec extract_from_text_lines
    """
    if not uploaded:
        return None
    if is_compressed_name(getattr(uploaded, "name", "")):
        st.error("Les fichiers compressés ne sont pas autorisés.")
        return None
    if getattr(uploaded, "size", 0) > 5 * 1024 * 1024:
        st.error("Fichier trop volumineux (> 5 Mo).")
        return None

    try:
        raw = uploaded.read()
        content = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception as e:
        st.error(f"Impossible de lire le fichier : {e}")
        return None

    # tenter CSV ';' puis ','
    for sep in (";", ","):
        try:
            df = pd.read_csv(StringIO(content), sep=sep)
            return df
        except Exception:
            continue

    # fallback texte libre
    df = extract_from_text_lines(content)
    return df


def load_robots_from_url(url: str) -> pd.DataFrame | None:
    """Télécharge et lit robots-ia.txt depuis GitHub (ou autre raw URL)."""
    if not url:
        st.error("URL du fichier robots-ia non fournie.")
        return None
    raw_url = to_raw_github(url)
    try:
        r = requests.get(raw_url, timeout=10)
        r.raise_for_status()
        robots_df = pd.read_csv(StringIO(r.text), sep=";")
        return robots_df
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier robots-ia depuis GitHub : {e}")
        return None


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise / détecte colonnes IP / User-Agent / Status-Code.
    Si elles sont absentes, extrait depuis le texte concaténé.
    """
    cols = {c.lower(): c for c in df.columns}
    mapping = {}
    for cand in ("ip", "client_ip", "remote_addr", "remoteaddr"):
        if cand in cols:
            mapping[cols[cand]] = "IP"
            break
    for cand in ("user-agent", "user_agent", "useragent", "ua"):
        if cand in cols:
            mapping[cols[cand]] = "User-Agent"
            break
    for cand in ("status-code", "status", "status_code", "statuscode"):
        if cand in cols:
            mapping[cols[cand]] = "Status-Code"
            break

    if mapping:
        df = df.rename(columns=mapping)

    if not all(c in df.columns for c in ("IP", "User-Agent", "Status-Code")):
        # si une colonne 'raw' existe, on l'utilise
        if "raw" in df.columns:
            return extract_from_text_lines("\n".join(df["raw"].astype(str).tolist()))
        # concaténation ligne par ligne et extraction
        text_rows = df.astype(str).agg(" ".join, axis=1).tolist()
        return extract_from_text_lines("\n".join(text_rows))

    # garantir présence des colonnes attendues
    for c in ("IP", "User-Agent", "Status-Code"):
        if c not in df.columns:
            df[c] = ""
    return df[["IP", "User-Agent", "Status-Code"] + [c for c in df.columns if c not in ("IP", "User-Agent", "Status-Code")]]


def analyze_crawler(df: pd.DataFrame, ip_prefix: str, ua_substr: str):
    """
    Cherche les lignes du DataFrame correspondant au crawler :
    - ip_prefix : startswith sur IP (si non vide)
    - ua_substr : contains (case-insensitive) sur User-Agent (si non vide)
    Retour : (nb_hits, counts_par_status, allowed_bool, matched_df)
    allowed_bool = True si tous les status rencontrés sont numériques et dans [200-499]
    """
    ip_prefix = str(ip_prefix or "").strip()
    ua_substr = str(ua_substr or "").strip()

    ip_mask = df["IP"].astype(str).str.startswith(ip_prefix, na=False) if ip_prefix else pd.Series([True] * len(df))
    ua_mask = df["User-Agent"].astype(str).str.contains(ua_substr, case=False, na=False) if ua_substr else pd.Series([True] * len(df))

    matched = df[ip_mask & ua_mask].copy()
    matched["__status__"] = matched["Status-Code"].astype(str).str.strip()
    counts = matched["__status__"].value_counts().to_dict()

    if matched.shape[0] == 0:
        return 0, {}, False, matched

    allowed = True
    for s in matched["__status__"].unique():
        if not str(s).isdigit():
            allowed = False
            break
        si = int(s)
        if not (200 <= si < 500):
            allowed = False
            break

    return matched.shape[0], counts, allowed, matched


# ------------------- Main flow -------------------
if uploaded_file and robots_url:
    # lecture du fichier uploadé
    df_raw = try_load_logs(uploaded_file)
    if df_raw is None:
        st.stop()

    st.success(f"Fichier importé : {uploaded_file.name}")
    st.write("Aperçu (premières lignes) :")
    st.dataframe(df_raw.head())

    # normalisation des colonnes pour obtenir IP/User-Agent/Status-Code
    df = normalize_columns(df_raw)

    # vérification minimale
    if not all(c in df.columns for c in ("IP", "User-Agent", "Status-Code")):
        st.error("Impossible d'extraire IP / User-Agent / Status-Code du fichier fourni.")
        st.write("Colonnes détectées :", list(df_raw.columns))
        st.stop()

    # chargement du fichier robots-ia depuis GitHub (raw URL)
    robots_df = load_robots_from_url(robots_url)
    if robots_df is None:
        st.stop()

    if not all(c in robots_df.columns for c in ("Nom", "IP", "User-Agent")):
        st.error("Le fichier robots-ia doit contenir les colonnes : Nom;IP;User-Agent")
        st.write("Colonnes trouvées dans robots-ia :", list(robots_df.columns))
        st.stop()

    st.success("Fichier robots-ia chargé.")
    st.write("Définitions des crawlers :", robots_df)

    # groupes demandés
    groups = {
        "Is Open AI crawling my website ?": [
            "ChatGPT Search Bot",
            "ChatGPT-User",
            "ChatGPT-GPTBot",
        ],
        "Is Perplexity crawling my website ?": [
            "Perplexity-Bot",
            "Perplexity-User",
        ],
        "Is Google crawling my website ?": [
            "Google-Gemini",
        ],
        "Is Mistral crawling my website ?": [
            "MistralAI-User",
        ],
    }

    st.markdown("---")
    st.markdown("## Résultats par IA")

    # boucle d'analyse
    for group_title, crawler_names in groups.items():
        st.markdown(f"### {group_title}")
        for cname in crawler_names:
            # récupérer lignes de définition correspondant au nom (contains)
            defs = robots_df[robots_df["Nom"].astype(str).str.contains(cname, case=False, na=False)]
            if defs.empty:
                st.write(f"- {cname} : définition introuvable dans robots-ia.")
                continue

            total_hits = 0
            total_counts = {}
            all_allowed = True
            any_hit = False
            example_rows = []

            for _, r in defs.iterrows():
                ip_pref = str(r["IP"]).strip()
                ua_sub = str(r["User-Agent"]).strip()
                hits, counts, allowed, matched = analyze_crawler(df, ip_pref, ua_sub)
                total_hits += hits
                any_hit = any_hit or (hits > 0)
                for k, v in counts.items():
                    total_counts[k] = total_counts.get(k, 0) + v
                if not allowed:
                    all_allowed = False
                if hits > 0:
                    example_rows.append(matched.head(3))

            if not any_hit:
                st.write(f"- {cname} : no – No hit detected by {cname}")
                continue

            result_yes = (total_hits > 0) and all_allowed
            st.write(f"- {cname} : {'yes' if result_yes else 'no'}  (hits = {total_hits})")
            st.write("  - Count par status code :", total_counts)
            if example_rows:
                ex = pd.concat(example_rows).drop_duplicates()
                st.write("  - Exemples de lignes matchées :")
                st.dataframe(ex[["IP", "User-Agent", "Status-Code"]].head(5))
        st.markdown("")

    st.info(
        "Interprétation : 'yes' = trouvé au moins une fois ET tous les hits ont des codes 2xx, 3xx ou 4xx. "
        "'no' = pas trouvé ou un/plusieurs hits ont rencontré des codes hors de ces familles (ex. 5xx ou statut non numérique)."
    )
else:
    st.info("Importez un fichier de logs et renseignez l'URL brute du fichier robots-ia.txt pour lancer l'analyse.")
