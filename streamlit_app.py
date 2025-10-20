import streamlit as st
import pandas as pd
import re
import requests

st.set_page_config(page_title="Is AI crawling my website ?")
st.title("🕵️ Is AI crawling my website ?")

# --- Constants ---
MAX_FILE_SIZE_MB = 5
CRAWLER_LIST_URL = "https://raw.githubusercontent.com/hoppy-lab/is-ai-crawling-my-website/e21bed70c4b9cdf9013f9c17da6490c95395f6c6/robots-ia.txt"

# --- Helper Functions ---
def detect_separator(sample_lines):
    separators = ["\t", ",", ";", "|", " "]
    scores = {}
    for sep in separators:
        counts = [len(line.split(sep)) for line in sample_lines if sep in line]
        if counts:
            scores[sep] = sum(counts) / len(counts)
    return max(scores, key=scores.get) if scores else None

def extract_fields(line, sep):
    ip_match = re.search(r"(\d{1,3}(?:\.\d{1,3}){2})", line)
    status_match = re.search(r"(?<!\.)\b([2-5][0-9]{2})\b(?!\.)", line)
    ua_match = re.search(r"([\w\-\/\.\s]+)$", line)
    if ip_match and status_match and ua_match:
        return ip_match.group(1), status_match.group(1), ua_match.group(1).strip()
    return None

@st.cache_data
def load_ia_crawlers():
    df = pd.read_csv(CRAWLER_LIST_URL, sep="\t")
    df = df.drop_duplicates(subset=["user_agent", "ip_prefix"])
    return df

def analyze_logs(lines, sep, ia_df):
    extracted = []
    for line in lines:
        fields = extract_fields(line, sep)
        if fields:
            extracted.append(fields)

    df_logs = pd.DataFrame(extracted, columns=["ip", "status", "user_agent"])
    df_logs["status"] = df_logs["status"].astype(int)

    results = {}
    for _, row in ia_df.iterrows():
        crawler_name = row["name"]
        ua_pattern = row["user_agent"].lower()
        ip_prefix = row["ip_prefix"]

        hits = df_logs[
            df_logs["user_agent"].str.lower().str.contains(ua_pattern) &
            df_logs["ip"].str.startswith(ip_prefix)
        ]

        if hits.empty:
            status = "No hit detected"
            status_counts = {}
        else:
            status_counts = hits["status"].value_counts().to_dict()
            if all(200 <= code < 500 for code in hits["status"]):
                status = "yes"
            else:
                status = "no"

        if crawler_name not in results:
            results[crawler_name] = {
                "status": status,
                "hits": status_counts,
                "lines": hits
            }

    return results, df_logs

# --- UI ---
uploaded_file = st.file_uploader("Upload your log file (max 5MB, no compressed files)", type=["txt", "log"])

if uploaded_file:
    if uploaded_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        st.error("File too large. Please upload a file smaller than 5MB.")
    else:
        lines = uploaded_file.read().decode("utf-8", errors="ignore").splitlines()
        sample_lines = lines[:20]
        sep = detect_separator(sample_lines)
        if not sep:
            st.error("Could not detect column separator.")
        else:
            st.success(f"Detected separator: '{sep.replace(chr(9), 'TAB')}'")
            ia_df = load_ia_crawlers()
            results, df_logs = analyze_logs(lines, sep, ia_df)

            for crawler, info in results.items():
                st.subheader(f"Crawler: {crawler}")
                st.markdown(f"**Status**: {info['status']}")
                if info['hits']:
                    for code, count in info['hits'].items():
                        st.markdown(f"- {code} : {count} hits")
                if not info['lines'].empty:
                    st.markdown("**Matched log entries:**")
                    st.dataframe(info['lines'])

            st.subheader("📄 All extracted log entries")
            st.dataframe(df_logs)
