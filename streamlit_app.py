import streamlit as st
import pandas as pd
import requests
import json

# --- FONCTION POUR CHARGER LES DONNÉES DES ROBOTS IA ---
@st.cache_data
def load_robots_data(url):
    """
    Charge le fichier JSON contenant les robots IA depuis l'URL fournie.
    Retourne une liste de dictionnaires contenant 'name' et 'user-agent'.
    """
    response = requests.get(url)
    robots = response.json()
    return robots

# --- FONCTION POUR PARCOURIR LES LOGS ET COMPTER LES OCCURRENCES ---
def analyze_logs(file, robots):
    """
    Analyse un fichier de logs ligne par ligne et compte combien de fois
    chaque user-agent IA est présent.
    
    Args:
        file : fichier de logs fourni par l'utilisateur
        robots : liste des robots IA avec 'name' et 'user-agent'
    
    Returns:
        results : dictionnaire {nom_robot: nombre_d_occurences}
    """
    # Initialisation du dictionnaire de résultats
    results = {robot['name']: 0 for robot in robots}

    # Lecture du fichier ligne par ligne
    for line in file:
        # Conversion en string (au cas où c'est un byte stream)
        line_str = line.decode('utf-8', errors='ignore') if isinstance(line, bytes) else line
        # Vérification de la présence de chaque user-agent dans la ligne
        for robot in robots:
            if robot['user-agent'] in line_str:
                results[robot['name']] += 1
    return results

# --- INTERFACE STREAMLIT ---
# Titre de l'application
st.title("is AI crawling my website")

# Description de l'application
st.write("""
This application allows you to check if AI bots are crawling your website.
Upload a log file (less than 50 MB) and it will scan for known AI crawlers.
""")

# Input fichier de logs
uploaded_file = st.file_uploader
