import streamlit as st
import pandas as pd
import re
import io
import shlex  # pour parser les chaînes avec guillemets

def parse_log(lines):
    data = {"ip": [], "status_code": [], "user_agent": []}
    ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    status_pattern = re.compile(r"\b\d{3}\b")

    for line in lines:
        # Utiliser shlex pour gérer les guillemets et espaces à l'intérieur
        try:
            parts = shlex.split(line)
        except:
            parts = line.strip().split()  # fallback simple si shlex échoue

        # Trouver l'IP (première occurrence dans la ligne)
        ip_match = ip_pattern.search(line)
        ip = ip_match.group(0) if ip_match else None

        # Trouver le status code (premier token de 3 chiffres)
        status_code = None
        for p in parts:
            if status_pattern.fullmatch(p):
                status_code = p
                break

        # User-Agent : dernière chaîne entre guillemets ou dernier token
        user_agent = None
        if len(parts) > 0:
            user_agent = parts[-1]

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

        # Parsing
        df = parse_log(lines)
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
