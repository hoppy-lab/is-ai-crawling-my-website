# app.py
"""
Streamlit app: "Is AI crawling my website?"
This app:
- télécharge une liste de robots IA (robots-ia.txt) (3 colonnes tabulées: name, user-agent fragment, IP prefix)
- permet à l'utilisateur d'uploader un fichier de logs (< 50 MB, non compressé)
- parcourt le fichier de logs ligne par ligne et compte combien de lignes contiennent chaque fragment de user-agent
- affiche un tableau récapitulatif (robot name + count)
Très commenté pour faciliter les adaptations.
"""

import io
import requests
import streamlit as st
import pandas as pd
from typing import List, Tuple

# ---------------------------------------------------------------------
# Config UI de la page Streamlit
# ---------------------------------------------------------------------
st.set_page_config(page_title="is AI crawlin my ebsitewebsite", layout="wide")

# Titre EXACT demandé (en anglais, tel quel)
st.title("is AI crawlin my ebsitewebsite")

# Description (en français) sous le titre
st.write(
    "Détecte la présence de bots AI dans vos logs. "
    "Uploadez un échantillon de vos logs (une journée par exemple) et l'application recherchera "
    "les user-agents présents dans notre base de robots IA."
)

# ---------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------
# URL du fichier de base fourni par l'utilisateur (raw GitHub)
ROBOTS_IA_URL = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/refs/heads/main/robots-ia.txt"

# Taille maximale autorisée (50 MB)
MAX_FILE_BYTES = 50 * 1024 * 1024

# Extensions compressées à refuser (liste non exhaustive)
COMPRESSED_EXTS = {".zip", ".gz", ".bz2", ".7z", ".rar", ".tar", ".xz"}

# ---------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_robots_list(url: str) -> List[Tuple[str, str, str]]:
    """
    Télécharge et parse le fichier robots-ia.txt depuis l'URL.
    Retourne une liste de tuples: (robot_name, ua_fragment, ip_prefix)
    - On suppose 3 colonnes séparées par tabulations, sans en-tête.
    - Les lignes vides sont ignorées.
    - On strip() les champs autour.
    Caching pour éviter de re-télécharger à chaque interaction.
    """
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    content = resp.text.splitlines()
    robots = []
    for raw in content:
        if not raw.strip():
            continue
        parts = raw.split("\t")
        # Si la ligne n'a pas exactement 3 colonnes, on essaye de s'adapter:
        if len(parts) < 3:
            # compléter par des chaînes vides si nécessaire
            parts = (parts + [""] * 3)[:3]
        robot_name = parts[0].strip()
        ua_fragment = parts[1].strip()
        ip_prefix = parts[2].strip()
        robots.append((robot_name, ua_fragment, ip_prefix))
    return robots

def is_compressed_filename(filename: str) -> bool:
    """
    Vérifie si le nom de fichier se termine par une extension compressée connue.
    """
    if not filename:
        return False
    lower = filename.lower()
    for ext in COMPRESSED_EXTS:
        if lower.endswith(ext):
            return True
    return False

# ---------------------------------------------------------------------
# Chargement de la base de robots IA
# ---------------------------------------------------------------------
with st.spinner("Fetching known AI crawlers list..."):
    try:
        robots = fetch_robots_list(ROBOTS_IA_URL)
    except Exception as e:
        st.error(f"Impossible de télécharger la liste des robots IA depuis {ROBOTS_IA_URL} : {e}")
        st.stop()

# Affichage compact de la liste (nom + fragment d'UA) pour information
if robots:
    st.markdown("**Robots IA connus (extrait de la base)** :")
    sample_df = pd.DataFrame(robots, columns=["robot_name", "ua_fragment", "ip_prefix"])
    # N'affiche que les colonnes utiles pour l'aperçu
    st.dataframe(sample_df[["robot_name", "ua_fragment", "ip_prefix"]], use_container_width=True)
else:
    st.warning("La liste des robots IA est vide.")

st.markdown("---")

# ---------------------------------------------------------------------
# Interface d'upload de fichier
# ---------------------------------------------------------------------
st.header("Upload your log file (one day sample)")

uploaded = st.file_uploader(
    "Sélectionnez un fichier de log (non compressé). Taille limite: 50 MB.",
    type=None,  # accepter tout type (mais nous filtrons les compressés par extension)
    accept_multiple_files=False
)

if uploaded is None:
    st.info("Aucun fichier uploadé — uploadez un fichier pour lancer l'analyse.")
    st.stop()

# Vérifications basiques
# 1) taille
if uploaded.size > MAX_FILE_BYTES:
    st.error(f"Fichier trop volumineux ({uploaded.size} bytes). Limite: {MAX_FILE_BYTES} bytes (50 MB).")
    st.stop()

# 2) extension compressée interdite
if is_compressed_filename(uploaded.name):
    st.error("Les fichiers compressés (.zip, .gz, .tar, etc.) ne sont pas acceptés. "
             "Merci de fournir le fichier de logs non compressé.")
    st.stop()

# ---------------------------------------------------------------------
# Comptage: pour chaque robot, on compte les lignes contenant ua_fragment
# ---------------------------------------------------------------------
st.info("Analyse en cours — lecture du fichier ligne par ligne (mémoire optimisée).")

# Préparer la structure de comptage
# dictionnaire: robot_name -> count
counts = {robot_name: 0 for robot_name, _, _ in robots}

# Préparer liste de fragments et mapping pour recherche rapide
# On utilisera une recherche case-insensitive
fragments = []
fragment_to_robot = {}  # fragment -> list of robot_names (au cas où plusieurs robots ont même fragment)
for robot_name, ua_fragment, ip_prefix in robots:
    frag = ua_fragment
    if frag == "":
        continue  # sauter les fragments vides (inutile à rechercher)
    frag_lower = frag.lower()
    fragments.append(frag_lower)
    fragment_to_robot.setdefault(frag_lower, []).append(robot_name)

# Lecture ligne par ligne: uploaded est un UploadedFile (io.BytesIO-like)
# On transforme en TextIOWrapper pour itérer en texte (utf-8 fallback)
try:
    text_stream = io.TextIOWrapper(uploaded, encoding="utf-8", errors="replace")
except Exception:
    # fallback si l'objet ne peut pas être wrapé directement
    uploaded.seek(0)
    raw_bytes = uploaded.read()
    text_stream = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace")

total_lines = 0
total_matches = 0

# IMPORTANT: si le nombre de fragments est élevé, la boucle imbriquée peut être coûteuse.
# Pour un usage d'échantillon journalier cela reste raisonnable.
for raw_line in text_stream:
    total_lines += 1
    line_lower = raw_line.lower()
    # Vérifier la présence de chaque fragment dans la ligne (sous-chaîne)
    for frag_lower in fragments:
        if frag_lower in line_lower:
            # incrémente une fois pour chaque robot associé à ce fragment
            for rname in fragment_to_robot.get(frag_lower, []):
                counts[rname] += 1
            total_matches += 1
            # NOTE: on ne "break" pas ici car une ligne peut contenir plusieurs fragments (plusieurs bots)
            # Si tu veux compter une ligne au maximum une seule fois, ajouter un break ici.
# Remettre le curseur du fichier (au cas où)
try:
    uploaded.seek(0)
except Exception:
    pass

# ---------------------------------------------------------------------
# Résultats: DataFrame et affichage
# ---------------------------------------------------------------------
# Construire DataFrame trié par compte décroissant
results = pd.DataFrame(
    [
        {"robot_name": rn, "ua_fragment": ua, "ip_prefix": ip, "count": counts.get(rn, 0)}
        for rn, ua, ip in robots
    ]
)

# Trier par nombre de détections
results = results.sort_values(by="count", ascending=False).reset_index(drop=True)

st.header("Résultats")
st.markdown(f"- Lignes analysées : **{total_lines}**")
st.markdown(f"- Occurrences totales détectées (toutes lignes confondues) : **{total_matches}**")

# Affiche seulement robots avec count > 0 en premier, mais propose le tableau complet
if results["count"].sum() == 0:
    st.warning("Aucune occurrence de fragments de user-agent IA trouvée dans ce fichier de logs.")
else:
    st.success(f"Robots IA détectés : {int((results['count'] > 0).sum())} robots ont au moins 1 occurrence.")

# Affichage du tableau complet
st.dataframe(results, use_container_width=True)

# Option : afficher uniquement les robots trouvés
st.markdown("#### Robots détectés (count > 0)")
detected = results[results["count"] > 0]
if not detected.empty:
    st.dataframe(detected, use_container_width=True)
else:
    st.markdown("_Aucun robot détecté._")

# ---------------------------------------------------------------------
# Conseils et prochaines étapes (suggestions)
# ---------------------------------------------------------------------
st.markdown("---")
st.subheader("Next steps / suggestions")
st.markdown(
    "- Vérifier les adresses IP correspondantes (colonne `ip_prefix`) pour confirmer l'appartenance des crawlers.\n"
    "- Ajouter une recherche par préfixe IP (si tu veux aussi filtrer par IP dans le log).\n"
    "- Si ton log est au format commun (combined log / nginx), on peut extraire la colonne User-Agent explicitement pour réduire les faux positifs.\n"
    "- Pour de très gros fichiers, envisager un passage en streaming sur disque ou un script en ligne de commande multi-thread."
)

# ---------------------------------------------------------------------
# Footer: lien vers la base des robots utilisée
# ---------------------------------------------------------------------
st.markdown("---")
st.caption("Base utilisée pour les fragments de user-agent et préfixes IP :")
st.write(ROBOTS_IA_URL)
