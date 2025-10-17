import streamlit as st

st.title("Is AI crawling my website ?")
st.write(
    "Fonctionne pour OpenAI, Google Extended, Perplexity"
)

st.write(
    "Déposez un fichier non compressé (texte). L'application affichera le nombre de lignes."
)

uploaded = st.file_uploader("Déposez un fichier ici (texte non compressé)")

if uploaded is not None:
    name = uploaded.name
    data = uploaded.read()

    # Détection simple des archives / binaires
    if name.lower().endswith(('.zip', '.gz', '.tar', '.tgz', '.bz2', '.xz', '.7z')):
        st.error("Fichier compressé détecté. Merci de déposer un fichier non compressé.")
    elif b'\x00' in data:
        st.error("Semble être un fichier binaire ou compressé. Merci de déposer un fichier texte non compressé.")
    else:
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            st.warning("Le fichier n'est pas en UTF-8. Décodage avec 'latin-1', ce qui peut entraîner des caractères incorrects.")
            try:
                text = data.decode('latin-1')
            except Exception:
                text = data.decode('utf-8', errors='replace')
                st.warning("Impossible de décoder avec 'latin-1'. Certains caractères ont été remplacés.")
        line_count = len(text.splitlines())
        st.success(f"Fichier : {name} — {line_count} ligne(s)")
# ...existing code...
