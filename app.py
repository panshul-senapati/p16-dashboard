import os
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import date, timedelta
import requests
import time

# ----------------------------
# CONFIGURE GITHUB TOKEN (FROM ENV VARIABLE ONLY)
# ----------------------------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

# ----------------------------
# PAGE CONFIGURATION
# ----------------------------
st.set_page_config(page_title="📊 GitHub Insights Dashboard", layout="wide")
st.title("📊 GitHub Insights Dashboard")

# ----------------------------
# SIDEBAR
# ----------------------------
st.sidebar.header("📁 Library Info & Filter")

repo_map = {
    "pandas": ("pandas-dev", "pandas"),
    "scikit-learn": ("scikit-learn", "scikit-learn"),
    "matplotlib": ("matplotlib", "matplotlib"),
    "tensorflow": ("tensorflow", "tensorflow"),
}
selected_lib = st.sidebar.selectbox(" Select Library:", list(repo_map.keys()))
owner, repo = repo_map[selected_lib]

today = date.today()
default_start = today - timedelta(days=180)

start_date = st.sidebar.date_input(" Select Start Date:", default_start, min_value=date(2010, 1, 1), max_value=today)
end_date = st.sidebar.date_input(" Select End Date:", today, min_value=start_date, max_value=today)

# ----------------------------
# LOAD CSV FUNCTION
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
# GITHUB RELEASE DOWNLOAD FUNCTION
# ----------------------------
def get_release_downloads(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        st.warning(f"Failed to fetch releases: Status {response.status_code}")
        return pd.DataFrame()
    releases = response.json()
    downloads_data = []
    for release in releases:
        tag = release.get("tag_name", "N/A")
        for asset in release.get("assets", []):
            downloads_data.append({
                "Release": tag,
                "Asset": asset.get("name", "unknown"),
                "Downloads": asset.get("download_count", 0),
                "Uploaded": asset.get("created_at", "")[:10]
            })
    return pd.DataFrame(downloads_data)

# ----------------------------
# GITHUB CONTRIBUTIONS FUNCTION
# ----------------------------
def get_weekly_contributions(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/stats/contributors"
    retry = 0
    while retry < 10:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 202:
            time.sleep(3)
            retry += 1
        else:
            break
    if response.status_code != 200:
        st.warning(f"Failed to fetch contributions: Status {response.status_code}")
        return pd.DataFrame()
    data = response.json()
    rows = []
    for contributor in data:
        for week in contributor["weeks"]:
            rows.append({
                "week": pd.to_datetime(week["w"], unit="s"),
                "commits": week["c"]
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.groupby("week", as_index=False)["commits"].sum()

# ----------------------------
# GITHUB ISSUES FUNCTION
# ----------------------------
def get_issues_over_time(owner, repo):
    issues = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page=100&page={page}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            st.warning(f"Issues API failed with status {response.status_code}")
            break
        page_data = response.json()
        if not page_data:
            break
        for issue in page_data:
            if "pull_request" not in issue:
                issues.append({"created_at": issue.get("created_at", "")})
        page += 1
        if page > 10:
            break
    df = pd.DataFrame(issues)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["created_at"]).dt.tz_localize(None).dt.normalize()
    return df.groupby("date").size().reset_index(name="issue_count")

# ----------------------------
# LOAD DATA
# ----------------------------
stars_df = load_and_parse_csv("data/github_stars.csv", "stars")
forks_df = load_and_parse_csv("data/github_forks.csv", "forks")
prs_df = load_and_parse_csv("data/github_pull_requests.csv", "pr_count")
downloads_df = load_and_parse_csv("data/github_downloads.csv", "downloads")
contributions_df = get_weekly_contributions(owner, repo)
issues_df = get_issues_over_time(owner, repo)

# ----------------------------
# FILTERING AND DISPLAY
# ----------------------------
if all([not df.empty for df in [stars_df, forks_df, prs_df, downloads_df]]):
    from_date = pd.to_datetime(start_date)
    to_date = pd.to_datetime(end_date)

    def filter_df(df, date_col="date"):
        return df[(df[date_col] >= from_date) & (df[date_col] <= to_date)]

    filtered_stars = filter_df(stars_df)
    filtered_forks = filter_df(forks_df)
    filtered_prs = filter_df(prs_df)
    filtered_downloads = filter_df(downloads_df)

    st.subheader(f"📊 Summary for {owner}/{repo}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Stars", int(filtered_stars["stars"].sum()))
    col2.metric("Total Forks", int(filtered_forks["forks"].sum()))
    col3.metric("Total PRs", int(filtered_prs["pr_count"].sum()))
    col4.metric("Total Downloads", int(filtered_downloads["downloads"].sum()))

    col1, col2 = st.columns(2)
    with col1:
        fig_stars = px.line(filtered_stars, x="date", y="stars", title=" Stars Over Time",
                            markers=True, template="plotly_white", color_discrete_sequence=["#FFD700"])
        st.plotly_chart(fig_stars, use_container_width=True)

    with col2:
        fig_forks = px.line(filtered_forks, x="date", y="forks", title=" Forks Over Time",
                            markers=True, template="plotly_white", color_discrete_sequence=["#1f77b4"])
        st.plotly_chart(fig_forks, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig_prs = px.line(filtered_prs, x="date", y="pr_count", title=" Pull Requests Over Time",
                          markers=True, template="plotly_white", color_discrete_sequence=["#FF7F0E"])
        st.plotly_chart(fig_prs, use_container_width=True)

    with col4:
        release_df = get_release_downloads(owner, repo)
        if not release_df.empty:
            fig_release = px.bar(release_df, x="Asset", y="Downloads", color="Release",
                                 title=" GitHub Asset Downloads per Release", text="Downloads",
                                 labels={"Downloads": "Download Count"})
            st.plotly_chart(fig_release, use_container_width=True)
        else:
            st.info("ℹ️ No GitHub release assets with downloads found.")

    # CONTRIBUTIONS
    if not contributions_df.empty:
        filtered_contributions = contributions_df[
            (contributions_df["week"] >= from_date) &
            (contributions_df["week"] <= to_date)
        ]
        if filtered_contributions.empty:
            st.info("ℹ️ No contribution data found in selected range.")
        else:
            contrib_fig = px.line(filtered_contributions, x="week", y="commits",
                                  title=" Weekly Contributions (Commits)", markers=True,
                                  template="plotly_white", color_discrete_sequence=["#2ca02c"])
            st.plotly_chart(contrib_fig, use_container_width=True)
    else:
        st.info("ℹ️ No contribution data found.")

    # ISSUES
    if not issues_df.empty:
        filtered_issues = issues_df[
            (issues_df["date"] >= from_date) &
            (issues_df["date"] <= to_date)
        ]
        if filtered_issues.empty:
            st.info("ℹ️ No issues data found in selected range.")
        else:
            issues_fig = px.line(filtered_issues, x="date", y="issue_count",
                                 title=" Issues Over Time", markers=True,
                                 template="plotly_white", color_discrete_sequence=["#d62728"])
            st.plotly_chart(issues_fig, use_container_width=True)
    else:
        st.info("ℹ️ No issues data found.")

    # DOWNLOAD BUTTONS
    st.markdown("###  Download Filtered Data")
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button("⬇️ Stars CSV", filtered_stars.to_csv(index=False), file_name="filtered_stars.csv")
    d2.download_button("⬇️ Forks CSV", filtered_forks.to_csv(index=False), file_name="filtered_forks.csv")
    d3.download_button("⬇️ PRs CSV", filtered_prs.to_csv(index=False), file_name="filtered_prs.csv")
    d4.download_button("⬇️ Downloads CSV", filtered_downloads.to_csv(index=False), file_name="filtered_downloads.csv")

else:
    st.error(" One or more input CSV files are missing, empty, or invalid.")

# ----------------------------
# HIDE STREAMLIT DEFAULT UI
# ----------------------------
hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)
