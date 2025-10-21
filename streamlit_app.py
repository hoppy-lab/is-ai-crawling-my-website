# Streamlit app: "is AI crawlin my ebsitewebsite"
# Purpose: allow a user to upload a single-day web server log (any textual format, <50MB, not compressed)
# The app downloads a base list of known AI crawlers (name, user-agent fragment, IP prefix)
# and scans the uploaded log line-by-line to count occurrences of user-agent fragments.

# --------------------------------------------------------------------------------
# Requirements: streamlit, pandas, requests
# Install with: pip install streamlit pandas requests
# Run with: streamlit run streamlit_is_ai_crawling_my_website.py
# --------------------------------------------------------------------------------

import io
import re
import requests
import pandas as pd
import streamlit as st
from typing import List, Tuple

# ---------------------- Configuration constants ----------------------
# Remote file containing the AI crawler database (3 columns: name, ua_fragment, ip_prefix)
ROBOTS_IA_URL = (
    "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.txt"
)
# Maximum allowed upload size in bytes (50 MB)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
# Compressed file extensions that we explicitly forbid
FORBIDDEN_COMPRESSED_EXTS = ('.zip', '.gz', '.bz2', '.xz', '.7z', '.rar', '.tgz')

# ---------------------- Helper functions ----------------------

def download_robots_db(url: str) -> List[Tuple[str, str, str]]:
    """
    Télécharge le fichier robots-ia.txt depuis l'URL fournie et le parse.
    Le fichier est attendu sans en-tête, tabulé, 3 colonnes:
      1) robot_name
      2) user-agent fragment (substring à rechercher)
      3) ip prefix (début d'IP, optionnelement utilisé plus tard)

    Retourne une liste de tuples (robot_name, ua_fragment, ip_prefix).
    En cas d'erreur, remonte une exception.
    """
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    text = resp.text

    robots = []
    # chaque ligne doit être tab-séparée en 3 champs
    for i, raw_line in enumerate(text.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) < 2:
            # ignore malformed lines mais continue
            continue
        # some lines might omit ip_prefix, on s'assure d'avoir 3 colonnes logiques
        name = parts[0].strip()
        ua_fragment = parts[1].strip()
        ip_prefix = parts[2].strip() if len(parts) >= 3 else ''
        robots.append((name, ua_fragment, ip_prefix))
    return robots


def is_forbidden_filename(filename: str) -> bool:
    """Vérifie si le nom de fichier semble être compressé (interdit)."""
    if not filename:
        return False
    lowered = filename.lower()
    return any(lowered.endswith(ext) for ext in FORBIDDEN_COMPRESSED_EXTS)


def iterate_lines(file_like: io.BytesIO, encoding_candidates=('utf-8', 'latin-1')):
    """
    Itère les lignes d'un objet bytes (BytesIO) sans charger tout le fichier en mémoire.
    Tente d'abord un décodage en utf-8, sinon latin-1.
    Rend chaque ligne sous forme de chaîne (str) sans le caractère final de saut de ligne.
    """
    # Tentative de lecture 'streaming' depuis BytesIO
    raw = file_like.getvalue()
    for enc in encoding_candidates:
        try:
            text = raw.decode(enc)
            # successful decode -> yield lines
            for line in text.splitlines():
                yield line
            return
        except Exception:
            # essaie le prochain encodage
            continue
    # Si aucun encodage n'a fonctionné, on décode en 'utf-8' en ignorant les erreurs
    text = raw.decode('utf-8', errors='ignore')
    for line in text.splitlines():
        yield line


# ---------------------- Streamlit UI & Logic ----------------------

# Metadonnées et titre (l'utilisateur a demandé un titre anglais très spécifique)
st.set_page_config(page_title='is AI crawlin my ebsitewebsite', layout='wide')

# Titre principal (doit afficher exactement la chaîne demandée)
st.title('is AI crawlin my ebsitewebsite')

# Description en dessous (en français, comme demandé)
st.markdown(
    'Détecte la présence de bots AI dans vos logs — téléversez un échantillon de logs (une journée par exemple) et l\'application cherchera les user-agents connus listés dans la base.'
)

# Téléversement de fichier: n'importe quel format sauf compressé, et <50MB
uploaded = st.file_uploader(
    label='Upload your log file (any text format, <50 MB, not compressed)',
    type=None,  # autorise tous les types de fichiers ; on filtrera côté code
    accept_multiple_files=False,
)

# Téléchargement et parsing de la base de robots IA
st.sidebar.header('Settings & info')
st.sidebar.markdown('La base de robots IA sera téléchargée depuis le dépôt GitHub indiqué.')

try:
    robots_db = download_robots_db(ROBOTS_IA_URL)
    st.sidebar.success(f'Loaded {len(robots_db)} AI crawler entries from remote DB.')
except Exception as e:
    st.sidebar.error('Impossible de télécharger la base de robots IA. Vérifiez votre connexion.')
    robots_db = []

# Afficher la table des robots connus (nom + user-agent fragment + ip prefix)
if robots_db:
    df_robots = pd.DataFrame(robots_db, columns=['robot_name', 'ua_fragment', 'ip_prefix'])
    with st.expander('Preview of known AI crawlers (from remote DB)'):
        st.dataframe(df_robots)

# Si aucun fichier téléversé -> guide d'utilisation
if uploaded is None:
    st.info('Téléversez un fichier de logs (texte), par ex. access.log. Taille maximale: 50 MB. Formats compressés interdits.')
    st.stop()

# Vérifications sur le fichier
# 1) taille
# st.file_uploader retourne un UploadedFile qui a .size et .name
file_size = uploaded.size if hasattr(uploaded, 'size') else None
file_name = uploaded.name if hasattr(uploaded, 'name') else ''

if file_size is not None and file_size > MAX_UPLOAD_BYTES:
    st.error(f'Le fichier dépasse la taille maximale autorisée de 50 MB (taille: {file_size} bytes).')
    st.stop()

# 2) extension (compressés interdits)
if is_forbidden_filename(file_name):
    st.error('Les fichiers compressés (zip, gz, bz2, xz, 7z, rar, tgz) sont interdits. Décompressez votre fichier puis téléversez le fichier texte résultant.')
    st.stop()

# Convertir le contenu téléversé en BytesIO pour itération
file_bytes = io.BytesIO(uploaded.getvalue())

# Préparer le compteur initial pour chaque robot
# On utilisera une recherche insensible à la casse sur la totalité de la ligne pour trouver le fragment du user-agent
counters = {name: 0 for (name, _, _) in robots_db}

# Pour l'utilisateur, afficher une option de prévisualisation et un bouton pour lancer l'analyse
with st.expander('Options d\'analyse'):
    preview_n = st.number_input('Preview first N lines of the uploaded file (0 = none)', min_value=0, max_value=10000, value=0, step=10)
    run_scan = st.button('Run scan')

# Prévisualisation si demandée
if preview_n > 0:
    preview_lines = []
    for i, line in enumerate(iterate_lines(file_bytes)):
        if i >= preview_n:
            break
        preview_lines.append(line)
    st.subheader('Preview')
    st.text('\n'.join(preview_lines))
    # Rewind file-like object for the real scan
    file_bytes.seek(0)

# Exécuter le scan si l'utilisateur clique
if not run_scan:
    st.info('Cliquez sur "Run scan" pour analyser le fichier de logs et compter les occurrences de user-agent.')
    st.stop()

# Réinitialiser le pointeur
file_bytes.seek(0)

# Pré-calc: on compile les expressions pour de meilleures performances
# On va chercher le substring du user-agent en insensible à la casse; on échappera le fragment pour sécurité regex
compiled_patterns = []
for name, ua_fragment, ip_prefix in robots_db:
    if not ua_fragment:
        # sauter si fragment vide
        continue
    # Escape pour éviter que des caractères spéciaux dans le fragment perturbent la regex
    esc = re.escape(ua_fragment)
    # pattern simple: chercher le fragment n'importe où, insensible à la casse
    pat = re.compile(esc, flags=re.IGNORECASE)
    compiled_patterns.append((name, pat))

# Scan ligne par ligne
line_count = 0
matched_line_count = 0
for line in iterate_lines(file_bytes):
    line_count += 1
    # pour chaque pattern on teste s'il apparaît dans la ligne
    any_match = False
    for name, pat in compiled_patterns:
        if pat.search(line):
            counters[name] += 1
            any_match = True
    if any_match:
        matched_line_count += 1

# Résultats: préparer un DataFrame trié par nombre décroissant
results = pd.DataFrame([
    {'robot_name': name, 'count_user_agent_matches': count}
    for name, count in counters.items()
])
results = results.sort_values(by='count_user_agent_matches', ascending=False).reset_index(drop=True)

# Afficher résumé
st.subheader('Scan results')
st.markdown(f'- Total lines scanned: **{line_count}**')
st.markdown(f'- Lines with at least one UA match: **{matched_line_count}**')

# Afficher tableau de résultats (seulement les robots avec >0 occurrences, et un onglet pour tout)
positive = results[results['count_user_agent_matches'] > 0]
if not positive.empty:
    st.success(f'Found {len(positive)} AI crawler(s) in your logs.')
    st.dataframe(positive)
else:
    st.warning('Aucun user-agent connu de la base n\'a été trouvé dans le fichier de logs.')

with st.expander('All known robots (full list and counts)'):
    st.dataframe(results)

# Option: export CSV des résultats
csv = results.to_csv(index=False)
st.download_button('Download results as CSV', data=csv, file_name='ai_crawlers_counts.csv', mime='text/csv')

# Fin de l'application
st.caption('Note: this tool searches user-agent fragments as provided in the remote list. False positives/negatives are possible depending on log format and how user-agents are logged.')
