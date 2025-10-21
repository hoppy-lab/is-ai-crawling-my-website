import streamlit as st
import pandas as pd
import requests
import io

# --- Titre et description de l'application ---
st.title("is AI crawlin my ebsitewebsite")
st.write("This application detects the presence of AI bots in your website logs.")

# --- Interface de chargement du fichier de logs ---
# L'utilisateur peut uploader un fichier de moins de 50 Mo, non compressé
uploaded_file = st.file_uploader(
    "Upload your log file (max 50
