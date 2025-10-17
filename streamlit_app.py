import re
from io import StringIO

import pandas as pd
import requests
import streamlit as st

# --- Configuration de la page Streamlit ---
# Définit le titre et le texte d'introduction de l'application.
st.set_page_config(page_title="Is AI crawling my website ?")
st.title("Is AI crawling my website ?")
st.markdown(
    """
- Importez un échantillon de vos logs (une journée par exemple) — max 5 Mo
- Aucun fichier compressé autorisé
- Le programme extrait automatiquement : IP, User-Agent, Status-Code (regex)
- Fournissez l'URL brute GitHub du fichier `robots-ia.txt` (format `Nom;IP;User-Agent`) ou laissez l'URL par défaut
"""
)

# --- Inputs utilisateur ---
# Champ pour uploader le fichier de logs (CSV ou TXT).
uploaded_file = st.file_uploader("Importez votre fichier de logs (CSV ou TXT, pas d'archive)", type=["csv", "txt"])
# Champ pour fournir l'URL raw GitHub du fichier robots-ia.txt
robots_url = st.text_input(
    "URL brute du fichier robots-ia.txt sur GitHub (raw)",
    "https://github.com/hoppy-lab/files/blob/main/robots-ia.txt",
)


# ---------- helpers ----------
# to_raw_github : convertit une URL GitHub avec /blob/ en URL "raw.githubusercontent.com"
# Ceci permet de récupérer directement le contenu brut du fichier sur GitHub.
def to_raw_github(url: str) -> str:
    if not url:
        return url
    # convert blob url to raw url if needed
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url


# is_compressed_name : vérifie si le nom de fichier indique une archive compressée.
# Utilisé pour refuser les fichiers compressés dès l'upload.
def is_compressed_name(name: str) -> bool:
    name = (name or "").lower()
    return any(name.endswith(ext) for ext in (".zip", ".gz", ".bz2", ".xz", ".7z", ".tar"))


# Regex simples pour détecter IP et codes HTTP dans du texte libre.
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
STATUS_RE = re.compile(r"\b([1-5]\d{2})\b")


# extract_from_text_lines :
# Si le fichier ne peut pas être lu comme CSV, on parse ligne par ligne :
# - on cherche la première IP par regex,
# - on cherche un code status 3 chiffres,
# - on tente d'extraire un User-Agent en prenant la dernière chaîne entre guillemets
#   ou en recherchant des tokens connus ("bot", "mozilla", "gptbot", etc.).
# Retour : DataFrame avec colonnes IP, User-Agent, Status-Code, raw.
def extract_from_text_lines(text: str) -> pd.DataFrame:
    rows = []
    known_ua_tokens = [
        "mozilla", "curl", "bot", "spider", "bingbot", "googlebot", "gptbot", "chatgpt", "perplexity", "mistral"
    ]

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # extraction IP
        ip_m = IP_RE.search(line)
        ip = ip_m.group() if ip_m else ""

        # extraction status
        status_m = STATUS_RE.search(line)
        status = status_m.group() if status_m else ""

        # tentative d'extraction du User-Agent : préférer la dernière chaîne entre guillemets
        quoted = re.findall(r'"([^"]{3,500})"', line)
        ua = ""
        if quoted:
            ua = quoted[-1].strip()
        else:
            # fallback : détecter autour d'un token connu
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


# try_load_logs :
# - vérifie nom de fichier et taille (< 5 Mo)
# - essaie de lire en CSV avec ';' puis ',' (les formats log courants)
# - si échec, lit tout le contenu comme texte et appelle extract_from_text_lines
# Retourne un DataFrame ou None en cas d'erreur.
def try_load_logs(uploaded) -> pd.DataFrame | None:
    if not uploaded:
        return None

    # vérifier extension archive et taille
    if is_compressed_name(getattr(uploaded, "name", "")):
        st.error("Les fichiers compressés ne sont pas autorisés.")
        return None
    if getattr(uploaded, "size", 0) > 5 * 1024 * 1024:
        st.error("Fichier trop volumineux (> 5 Mo).")
        return None

    # lire le contenu en mémoire (texte)
    try:
        raw = uploaded.read()
        if isinstance(raw, bytes):
            content = raw.decode("utf-8", errors="replace")
        else:
            content = str(raw)
    except Exception as e:
        st.error(f"Impossible de lire le fichier : {e}")
        return None

    # tentative : CSV avec séparation ';' puis ','
    for sep in (";", ","):
        try:
            df = pd.read_csv(StringIO(content), sep=sep)
            # si la lecture CSV réussit, on renvoie le DataFrame brut
            return df
        except Exception:
            continue

    # fallback : contenu libre -> extraction par regex/heuristiques
    df = extract_from_text_lines(content)
    return df


# load_robots_from_url :
# - convertit l'URL GitHub en URL raw si besoin
# - télécharge le fichier robots-ia.txt et le lit en CSV (';' sep)
# - attente d'un format Nom;IP;User-Agent
def load_robots_from_url(url: str) -> pd.DataFrame | None:
    if not url:
        st.error("URL du fichier robots-ia non fournie.")
        return None
    raw_url = to_raw_github(url)
    try:
        r = requests.get(raw_url, timeout=10)
        r.raise_for_status()
        text = r.text
        robots_df = pd.read_csv(StringIO(text), sep=";")
        return robots_df
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier robots-ia depuis GitHub : {e}")
        return None


# normalize_columns :
# - renomme automatiquement des colonnes communes en IP / User-Agent / Status-Code
# - si ces colonnes n'existent pas, construit un DataFrame par extraction depuis le texte brut
# Ceci permet d'accepter des logs très divers sans format strict.
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
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
        # renommage pour standardiser les colonnes
        df = df.rename(columns=mapping)

    if not all(c in df.columns for c in ("IP", "User-Agent", "Status-Code")):
        # si on n'a pas les colonnes requises, tenter d'extraire depuis une colonne 'raw' si présente
        if "raw" in df.columns:
            return extract_from_text_lines("\n".join(df["raw"].astype(str).tolist()))
        # sinon concaténer les colonnes en texte et extraire via heuristiques
        text_rows = df.astype(str).agg(" ".join, axis=1).tolist()
        return extract_from_text_lines("\n".join(text_rows))

    # garantir la présence des colonnes attendues
    for c in ("IP", "User-Agent", "Status-Code"):
        if c not in df.columns:
            df[c] = ""
    # retour : DataFrame avec colonnes standard en tête
    return df[["IP", "User-Agent", "Status-Code"] + [c for c in df.columns if c not in ("IP", "User-Agent", "Status-Code")]]


# analyze_crawler :
# - ip_prefix : correspondance "startswith" sur la colonne IP
# - ua_substr : correspondance "contains" (case-insensitive) sur le User-Agent
# - renvoie : nombre de hits, counts par status, bool allowed (tous status 200-499), et les lignes matchées
def analyze_crawler(df: pd.DataFrame, ip_prefix: str, ua_substr: str):
    ip_prefix = str(ip_prefix or "").strip()
    ua_substr = str(ua_substr or "").strip()

    if ip_prefix:
        ip_mask = df["IP"].astype(str).str.startswith(ip_prefix, na=False)
    else:
        ip_mask = pd.Series([True] * len(df))

    if ua_substr:
        ua_mask = df["User-Agent"].astype(str).str.contains(ua_substr, case=False, na=False)
    else:
        ua_mask = pd.Series([True] * len(df))

    matched = df[ip_mask & ua_mask].copy()
    matched["__status__"] = matched["Status-Code"].astype(str).str.strip()

    counts = matched["__status__"].value_counts().to_dict()

    # si pas de hit, on renvoie 0 et allowed=False (aucune détection)
    if matched.shape[0] == 0:
        return 0, {}, False, matched

    # allowed = True seulement si tous les status sont numériques et entre 200 et 499 inclus
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


# ---------- main ----------
# Logique principale : charger le fichier uploadé, normaliser, charger robots-ia et analyser par groupe demandé.
if uploaded_file and robots_url:
    # lire le fichier de logs (CSV ou texte libre)
    df_raw = try_load_logs(uploaded_file)
    if df_raw is None:
        st.stop()

    st.success(f"Fichier importé : {uploaded_file.name}")
    st.write("Aperçu (premières lignes) :")
    st.dataframe(df_raw.head())

    # normaliser les colonnes pour obtenir IP/User-Agent/Status-Code
    df = normalize_columns(df_raw)

    # vérification finale des colonnes requises
    if not all(c in df.columns for c in ("IP", "User-Agent", "Status-Code")):
        st.error("Impossible d'extraire IP / User-Agent / Status-Code du fichier fourni.")
        st.write("Colonnes détectées :", list(df_raw.columns))
        st.stop()

    # charger la liste des robots depuis GitHub (fichier fourni)
    robots_df = load_robots_from_url(robots_url)
    if robots_df is None:
        st.stop()

    # vérification du format attendu du fichier robots-ia
    if not all(c in robots_df.columns for c in ("Nom", "IP", "User-Agent")):
        st.error("Le fichier robots-ia doit contenir les colonnes : Nom;IP;User-Agent")
        st.write("Colonnes trouvées dans robots-ia :", list(robots_df.columns))
        st.stop()

    st.success("Fichier robots-ia chargé.")
    st.write("Définitions des crawlers :", robots_df)

    # groupes et noms demandés par le cahier des charges
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

    # boucle sur chaque groupe et chaque crawler demandé
    for group_title, crawler_names in groups.items():
        st.markdown(f"### {group_title}")
        for cname in crawler_names:
            # chercher les définitions dans robots_df dont la colonne Nom contient le nom du crawler (case-insensitive)
            defs = robots_df[robots_df["Nom"].astype(str).str.contains(cname, case=False, na=False)]
            if defs.empty:
                st.write(f"- {cname} : définition introuvable dans robots-ia.")
                continue

            total_hits = 0
            total_counts = {}
            all_allowed = True
            any_hit = False
            example_rows = []

            # pour chaque définition (il peut y avoir plusieurs lignes pour un même crawler),
            # on cumule les hits et les counts
            for _, r in defs.iterrows():
                ip_pref = str(r["IP"]).strip()          # correspondance "commence par" sur l'IP
                ua_sub = str(r["User-Agent"]).strip()   # correspondance "contient" sur le UA
                hits, counts, allowed, matched = analyze_crawler(df, ip_pref, ua_sub)
                total_hits += hits
                any_hit = any_hit or (hits > 0)
                for k, v in counts.items():
                    total_counts[k] = total_counts.get(k, 0) + v
                if not allowed:
                    all_allowed = False
                if hits > 0:
                    example_rows.append(matched.head(3))

            # cas : aucun hit
            if not any_hit:
                st.write(f"- {cname} : no – No hit detected by {cname}")
                continue

            # yes si au moins un hit et tous les codes rencontrés sont dans 2xx/3xx/4xx
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
    # message affiché quand les inputs ne sont pas encore fournis
    st.info("Importez un fichier de logs et renseignez l'URL brute du fichier robots-ia.txt pour lancer l'analyse.")
```# filepath: /workspaces/blank-app/streamlit_app.py
import re
from io import StringIO

import pandas as pd
import requests
import streamlit as st

# --- Configuration de la page Streamlit ---
# Définit le titre et le texte d'introduction de l'application.
st.set_page_config(page_title="Is AI crawling my website ?")
st.title("Is AI crawling my website ?")
st.markdown(
    """
- Importez un échantillon de vos logs (une journée par exemple) — max 5 Mo
- Aucun fichier compressé autorisé
- Le programme extrait automatiquement : IP, User-Agent, Status-Code (regex)
- Fournissez l'URL brute GitHub du fichier `robots-ia.txt` (format `Nom;IP;User-Agent`) ou laissez l'URL par défaut
"""
)

# --- Inputs utilisateur ---
# Champ pour uploader le fichier de logs (CSV ou TXT).
uploaded_file = st.file_uploader("Importez votre fichier de logs (CSV ou TXT, pas d'archive)", type=["csv", "txt"])
# Champ pour fournir l'URL raw GitHub du fichier robots-ia.txt
robots_url = st.text_input(
    "URL brute du fichier robots-ia.txt sur GitHub (raw)",
    "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/e21bed70c4b9cdf9013f9c17da6490c95395f6c6/robots-ia.txt",
)


# ---------- helpers ----------
# to_raw_github : convertit une URL GitHub avec /blob/ en URL "raw.githubusercontent.com"
# Ceci permet de récupérer directement le contenu brut du fichier sur GitHub.
def to_raw_github(url: str) -> str:
    if not url:
        return url
    # convert blob url to raw url if needed
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url


# is_compressed_name : vérifie si le nom de fichier indique une archive compressée.
# Utilisé pour refuser les fichiers compressés dès l'upload.
def is_compressed_name(name: str) -> bool:
    name = (name or "").lower()
    return any(name.endswith(ext) for ext in (".zip", ".gz", ".bz2", ".xz", ".7z", ".tar"))


# Regex simples pour détecter IP et codes HTTP dans du texte libre.
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
STATUS_RE = re.compile(r"\b([1-5]\d{2})\b")


# extract_from_text_lines :
# Si le fichier ne peut pas être lu comme CSV, on parse ligne par ligne :
# - on cherche la première IP par regex,
# - on cherche un code status 3 chiffres,
# - on tente d'extraire un User-Agent en prenant la dernière chaîne entre guillemets
#   ou en recherchant des tokens connus ("bot", "mozilla", "gptbot", etc.).
# Retour : DataFrame avec colonnes IP, User-Agent, Status-Code, raw.
def extract_from_text_lines(text: str) -> pd.DataFrame:
    rows = []
    known_ua_tokens = [
        "mozilla", "curl", "bot", "spider", "bingbot", "googlebot", "gptbot", "chatgpt", "perplexity", "mistral"
    ]

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # extraction IP
        ip_m = IP_RE.search(line)
        ip = ip_m.group() if ip_m else ""

        # extraction status
        status_m = STATUS_RE.search(line)
        status = status_m.group() if status_m else ""

        # tentative d'extraction du User-Agent : préférer la dernière chaîne entre guillemets
        quoted = re.findall(r'"([^"]{3,500})"', line)
        ua = ""
        if quoted:
            ua = quoted[-1].strip()
        else:
            # fallback : détecter autour d'un token connu
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


# try_load_logs :
# - vérifie nom de fichier et taille (< 5 Mo)
# - essaie de lire en CSV avec ';' puis ',' (les formats log courants)
# - si échec, lit tout le contenu comme texte et appelle extract_from_text_lines
# Retourne un DataFrame ou None en cas d'erreur.
def try_load_logs(uploaded) -> pd.DataFrame | None:
    if not uploaded:
        return None

    # vérifier extension archive et taille
    if is_compressed_name(getattr(uploaded, "name", "")):
        st.error("Les fichiers compressés ne sont pas autorisés.")
        return None
    if getattr(uploaded, "size", 0) > 5 * 1024 * 1024:
        st.error("Fichier trop volumineux (> 5 Mo).")
        return None

    # lire le contenu en mémoire (texte)
    try:
        raw = uploaded.read()
        if isinstance(raw, bytes):
            content = raw.decode("utf-8", errors="replace")
        else:
            content = str(raw)
    except Exception as e:
        st.error(f"Impossible de lire le fichier : {e}")
        return None

    # tentative : CSV avec séparation ';' puis ','
    for sep in (";", ","):
        try:
            df = pd.read_csv(StringIO(content), sep=sep)
            # si la lecture CSV réussit, on renvoie le DataFrame brut
            return df
        except Exception:
            continue

    # fallback : contenu libre -> extraction par regex/heuristiques
    df = extract_from_text_lines(content)
    return df


# load_robots_from_url :
# - convertit l'URL GitHub en URL raw si besoin
# - télécharge le fichier robots-ia.txt et le lit en CSV (';' sep)
# - attente d'un format Nom;IP;User-Agent
def load_robots_from_url(url: str) -> pd.DataFrame | None:
    if not url:
        st.error("URL du fichier robots-ia non fournie.")
        return None
    raw_url = to_raw_github(url)
    try:
        r = requests.get(raw_url, timeout=10)
        r.raise_for_status()
        text = r.text
        robots_df = pd.read_csv(StringIO(text), sep=";")
        return robots_df
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier robots-ia depuis GitHub : {e}")
        return None


# normalize_columns :
# - renomme automatiquement des colonnes communes en IP / User-Agent / Status-Code
# - si ces colonnes n'existent pas, construit un DataFrame par extraction depuis le texte brut
# Ceci permet d'accepter des logs très divers sans format strict.
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
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
        # renommage pour standardiser les colonnes
        df = df.rename(columns=mapping)

    if not all(c in df.columns for c in ("IP", "User-Agent", "Status-Code")):
        # si on n'a pas les colonnes requises, tenter d'extraire depuis une colonne 'raw' si présente
        if "raw" in df.columns:
            return extract_from_text_lines("\n".join(df["raw"].astype(str).tolist()))
        # sinon concaténer les colonnes en texte et extraire via heuristiques
        text_rows = df.astype(str).agg(" ".join, axis=1).tolist()
        return extract_from_text_lines("\n".join(text_rows))

    # garantir la présence des colonnes attendues
    for c in ("IP", "User-Agent", "Status-Code"):
        if c not in df.columns:
            df[c] = ""
    # retour : DataFrame avec colonnes standard en tête
    return df[["IP", "User-Agent", "Status-Code"] + [c for c in df.columns if c not in ("IP", "User-Agent", "Status-Code")]]


# analyze_crawler :
# - ip_prefix : correspondance "startswith" sur la colonne IP
# - ua_substr : correspondance "contains" (case-insensitive) sur le User-Agent
# - renvoie : nombre de hits, counts par status, bool allowed (tous status 200-499), et les lignes matchées
def analyze_crawler(df: pd.DataFrame, ip_prefix: str, ua_substr: str):
    ip_prefix = str(ip_prefix or "").strip()
    ua_substr = str(ua_substr or "").strip()

    if ip_prefix:
        ip_mask = df["IP"].astype(str).str.startswith(ip_prefix, na=False)
    else:
        ip_mask = pd.Series([True] * len(df))

    if ua_substr:
        ua_mask = df["User-Agent"].astype(str).str.contains(ua_substr, case=False, na=False)
    else:
        ua_mask = pd.Series([True] * len(df))

    matched = df[ip_mask & ua_mask].copy()
    matched["__status__"] = matched["Status-Code"].astype(str).str.strip()

    counts = matched["__status__"].value_counts().to_dict()

    # si pas de hit, on renvoie 0 et allowed=False (aucune détection)
    if matched.shape[0] == 0:
        return 0, {}, False, matched

    # allowed = True seulement si tous les status sont numériques et entre 200 et 499 inclus
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


# ---------- main ----------
# Logique principale : charger le fichier uploadé, normaliser, charger robots-ia et analyser par groupe demandé.
if uploaded_file and robots_url:
    # lire le fichier de logs (CSV ou texte libre)
    df_raw = try_load_logs(uploaded_file)
    if df_raw is None:
        st.stop()

    st.success(f"Fichier importé : {uploaded_file.name}")
    st.write("Aperçu (premières lignes) :")
    st.dataframe(df_raw.head())

    # normaliser les colonnes pour obtenir IP/User-Agent/Status-Code
    df = normalize_columns(df_raw)

    # vérification finale des colonnes requises
    if not all(c in df.columns for c in ("IP", "User-Agent", "Status-Code")):
        st.error("Impossible d'extraire IP / User-Agent / Status-Code du fichier fourni.")
        st.write("Colonnes détectées :", list(df_raw.columns))
        st.stop()

    # charger la liste des robots depuis GitHub (fichier fourni)
    robots_df = load_robots_from_url(robots_url)
    if robots_df is None:
        st.stop()

    # vérification du format attendu du fichier robots-ia
    if not all(c in robots_df.columns for c in ("Nom", "IP", "User-Agent")):
        st.error("Le fichier robots-ia doit contenir les colonnes : Nom;IP;User-Agent")
        st.write("Colonnes trouvées dans robots-ia :", list(robots_df.columns))
        st.stop()

    st.success("Fichier robots-ia chargé.")
    st.write("Définitions des crawlers :", robots_df)

    # groupes et noms demandés par le cahier des charges
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

    # boucle sur chaque groupe et chaque crawler demandé
    for group_title, crawler_names in groups.items():
        st.markdown(f"### {group_title}")
        for cname in crawler_names:
            # chercher les définitions dans robots_df dont la colonne Nom contient le nom du crawler (case-insensitive)
            defs = robots_df[robots_df["Nom"].astype(str).str.contains(cname, case=False, na=False)]
            if defs.empty:
                st.write(f"- {cname} : définition introuvable dans robots-ia.")
                continue

            total_hits = 0
            total_counts = {}
            all_allowed = True
            any_hit = False
            example_rows = []

            # pour chaque définition (il peut y avoir plusieurs lignes pour un même crawler),
            # on cumule les hits et les counts
            for _, r in defs.iterrows():
                ip_pref = str(r["IP"]).strip()          # correspondance "commence par" sur l'IP
                ua_sub = str(r["User-Agent"]).strip()   # correspondance "contient" sur le UA
                hits, counts, allowed, matched = analyze_crawler(df, ip_pref, ua_sub)
                total_hits += hits
                any_hit = any_hit or (hits > 0)
                for k, v in counts.items():
                    total_counts[k] = total_counts.get(k, 0) + v
                if not allowed:
                    all_allowed = False
                if hits > 0:
                    example_rows.append(matched.head(3))

            # cas : aucun hit
            if not any_hit:
                st.write(f"- {cname} : no – No hit detected by {cname}")
                continue

            # yes si au moins un hit et tous les codes rencontrés sont dans 2xx/3xx/4xx
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
    # message affiché quand les inputs ne sont pas encore fournis
    st.info("Importez un fichier de logs et renseignez l'URL brute du fichier robots-ia.txt pour lancer l'analyse.")
