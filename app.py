import os
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime, date, timedelta

# ----------------------------
# PAGE CONFIGURATION
# ----------------------------
st.set_page_config(page_title="📊 GitHub Insights Dashboard", layout="wide")
st.title("📊 GitHub Insights Dashboard")

# ----------------------------
# SIDEBAR
# ----------------------------
st.sidebar.header("📁 Library Info & Filter")

# Repository options
repo_map = {
    "pandas": ("pandas-dev", "pandas"),
    "scikit-learn": ("scikit-learn", "scikit-learn"),
    "matplotlib": ("matplotlib", "matplotlib"),
    "tensorflow": ("tensorflow", "tensorflow"),
}
selected_lib = st.sidebar.selectbox("📦 Select Library:", list(repo_map.keys()))
owner, repo = repo_map[selected_lib]

# Date Range Filter
today = date.today()
default_start = today - timedelta(days=180)
start_date, end_date = st.sidebar.date_input(
    "📅 Select Date Range:",
    [default_start, today],
    min_value=date(2010, 1, 1),
    max_value=today
)

# ----------------------------
# LOAD DATA FUNCTION
# ----------------------------
@st.cache_data
def load_and_parse_csv(path, expected_col):
    if not os.path.exists(path):
        st.warning(f"⚠️ File not found: {path}")
        return pd.DataFrame(columns=["date", expected_col])
    df = pd.read_csv(path)
    if "date" not in df.columns or expected_col not in df.columns:
        st.error(f"⚠️ The file {path} must contain 'date' and '{expected_col}' columns.")
        return pd.DataFrame(columns=["date", expected_col])
    df["date"] = pd.to_datetime(df["date"], errors='coerce')
    df.dropna(subset=["date"], inplace=True)
    return df

# ----------------------------
# LOAD ALL DATA
# ----------------------------
stars_df = load_and_parse_csv("data/github_stars.csv", "stars")
forks_df = load_and_parse_csv("data/github_forks.csv", "forks")
prs_df = load_and_parse_csv("data/github_pull_requests.csv", "pr_count")
downloads_df = load_and_parse_csv("data/github_downloads.csv", "downloads")

# ----------------------------
# FILTERING
# ----------------------------
if all([not df.empty for df in [stars_df, forks_df, prs_df, downloads_df]]):
    from_date = pd.to_datetime(start_date[0])
    to_date = pd.to_datetime(start_date[1]) if len(start_date) > 1 else pd.to_datetime(start_date[0])

    def filter_df(df):
        return df[(df["date"] >= from_date) & (df["date"] <= to_date)]

    filtered_stars = filter_df(stars_df)
    filtered_forks = filter_df(forks_df)
    filtered_prs = filter_df(prs_df)
    filtered_downloads = filter_df(downloads_df)

    # ----------------------------
    # SUMMARY METRICS
    # ----------------------------
    st.subheader(f"📊 Summary for {owner}/{repo}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Stars", int(filtered_stars["stars"].sum()))
    col2.metric("Total Forks", int(filtered_forks["forks"].sum()))
    col3.metric("Total PRs", int(filtered_prs["pr_count"].sum()))
    col4.metric("Total Downloads", int(filtered_downloads["downloads"].sum()))

    # ----------------------------
    # CHARTS
    # ----------------------------
    col1, col2 = st.columns(2)
    with col1:
        fig_stars = px.line(
            filtered_stars, x="date", y="stars", title="⭐ Stars Over Time",
            markers=True, template="plotly_white", color_discrete_sequence=["#FFD700"]
        )
        st.plotly_chart(fig_stars, use_container_width=True)

    with col2:
        fig_forks = px.line(
            filtered_forks, x="date", y="forks", title="🍴 Forks Over Time",
            markers=True, template="plotly_white", color_discrete_sequence=["#1f77b4"]
        )
        st.plotly_chart(fig_forks, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig_prs = px.line(
            filtered_prs, x="date", y="pr_count", title="📥 Pull Requests Over Time",
            markers=True, template="plotly_white", color_discrete_sequence=["#FF7F0E"]
        )
        st.plotly_chart(fig_prs, use_container_width=True)

    with col4:
        fig_downloads = px.line(
            filtered_downloads, x="date", y="downloads", title="⬇️ Downloads Over Time",
            markers=True, template="plotly_white", color_discrete_sequence=["#2CA02C"]
        )
        st.plotly_chart(fig_downloads, use_container_width=True)

    # ----------------------------
    # DOWNLOAD BUTTONS
    # ----------------------------
    st.markdown("### 📤 Download Filtered Data")
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("⬇️ Stars CSV", filtered_stars.to_csv(index=False), file_name="filtered_stars.csv")
    d2.download_button("⬇️ Forks CSV", filtered_forks.to_csv(index=False), file_name="filtered_forks.csv")
    d3.download_button("⬇️ PRs CSV", filtered_prs.to_csv(index=False), file_name="filtered_prs.csv")
    d4.download_button("⬇️ Downloads CSV", filtered_downloads.to_csv(index=False), file_name="filtered_downloads.csv")

else:
    st.error("🚫 One or more input CSV files are missing, empty, or invalid.")

# ----------------------------
# HIDE STREAMLIT UI
# ----------------------------
hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)
