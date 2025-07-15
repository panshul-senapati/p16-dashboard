import os
import pandas as pd
import plotly.express as px
import streamlit as st
import datetime

# ----------------------------
# PAGE CONFIGURATION
# ----------------------------
st.set_page_config(page_title="📊 P16 GitHub History Dashboard", layout="wide")

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
today = datetime.date.today()
default_start = today - datetime.timedelta(days=180)

start_date, end_date = st.sidebar.date_input(
    "📅 Select Date Range:",
    [default_start, today],
    min_value=datetime.date(2010, 1, 1),
    max_value=today
)

# ----------------------------
# HELPER FUNCTION TO LOAD CSV
# ----------------------------
@st.cache_data
def load_data(filename):
    if os.path.exists(filename):
        df = pd.read_csv(filename, parse_dates=["date"])
        return df
    else:
        st.warning(f"⚠️ {filename} not found.")
        return pd.DataFrame()

# ----------------------------
# LOAD STARS AND FORKS
# ----------------------------
stars_path = f"data/github_stars.csv"
forks_path = f"data/github_forks.csv"

stars_df = load_data(stars_path)
forks_df = load_data(forks_path)

# ----------------------------
# FILTER BY DATE RANGE
# ----------------------------
if not stars_df.empty and not forks_df.empty:
    stars_df = stars_df[(stars_df['date'] >= pd.to_datetime(start_date)) & (stars_df['date'] <= pd.to_datetime(end_date))]
    forks_df = forks_df[(forks_df['date'] >= pd.to_datetime(start_date)) & (forks_df['date'] <= pd.to_datetime(end_date))]

    # ----------------------------
    # DISPLAY GRAPHS
    # ----------------------------
    st.title(f"📈 GitHub History: {owner}/{repo}")
    st.markdown("Visualizing historical data using GitHub's GraphQL API and stored CSV snapshots.")

    st.subheader("⭐ Stargazers Over Time")
    fig_stars = px.line(
        stars_df,
        x="date",
        y="stars",
        title="Cumulative Stars Over Time",
        markers=True,
        template="plotly_white",
        color_discrete_sequence=["#FFD700"]
    )
    st.plotly_chart(fig_stars, use_container_width=True)

    st.subheader("🍴 Forks Over Time")
    fig_forks = px.line(
        forks_df,
        x="date",
        y="forks",
        title="Cumulative Forks Over Time",
        markers=True,
        template="plotly_white",
        color_discrete_sequence=["#1f77b4"]
    )
    st.plotly_chart(fig_forks, use_container_width=True)
else:
    st.warning("Data not available. Please make sure `github_stars.csv` and `github_forks.csv` exist inside the `data/` folder.")

# ----------------------------
# OPTIONAL: HIDE STREAMLIT STYLE
# ----------------------------
hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)
