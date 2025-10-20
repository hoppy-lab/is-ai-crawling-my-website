import streamlit as st
import pandas as pd
import re
import io

def detect_separator(line: str) -> str:
    """
    Détecte le séparateur principal (hors '.') en se basant sur la première ligne.
    Hypothèse : séparateur fréquent et répétitif (espace, tab, ';', '|', ',').
    """
    possible_seps = [",", ";", "|", "\t", " "]
    counts = {sep: line.count(sep) for sep in possible_seps if sep != "."}
    return max(counts, key=counts.get) if counts else " "

def parse_log(lines, sep):
    data = {"ip": [], "status_code": [], "user_agent": []}
    ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

    for line in lines:
        parts = line.strip().split(sep)

        # Trouver l'IP
        ip_match = ip_pattern.search(line)
        ip = ip_match.group(0) if ip_match else None

        # Trouver un code status HTTP (3 chiffres isolés entre séparateurs)
        status_code = None
        for p in parts:
            if re.fullmatch(r"\d{3}", p):
                status_code = p
                break

        # User-Agent supposé être le dernier champ complexe
        user_agent = parts[-1] if len(parts) > 1 else None

        if ip and status_code and user_agent:
            data["ip"].append(ip)
            data["status_code"].append(status_code)
            data["user_agent"].append(user_agent)

    return pd.DataFrame(data)

def main():
    st.title("Analyseur de Logs Serveur")

    uploaded_file = st.file_uploader("Choisissez un fichier de logs", type=["log", "txt", "csv"])
    
    if uploaded_file is not None:
        # Lire le fichier
        lines = uploaded_file.getvalue().decode("utf-8", errors="ignore").splitlines()

        if not lines:
            st.error("Le fichier est vide.")
            return

        # Détection du séparateur
        sep = detect_separator(lines[0])
        st.write(f"Séparateur détecté : `{repr(sep)}`")

        # Parsing
        df = parse_log(lines, sep)
        st.dataframe(df)

        # Téléchargement CSV
        if not df.empty:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            st.download_button(
                label="Télécharger le fichier CSV",
                data=csv_buffer.getvalue(),
                file_name="logs_extraits.csv",
                mime="text/csv"
            )
        else:
            st.warning("Aucune donnée exploitable trouvée.")

if __name__ == "__main__":
    main()
