import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="GitHub Downloads", layout="wide")
st.title("📥 GitHub Release Download Statistics")

# Your GitHub repo info
username = "panshul-senapati"
repo = "p16-dashboard"
url = f"https://api.github.com/repos/{username}/{repo}/releases"

response = requests.get(url)
if response.status_code != 200:
    st.error("❌ Could not fetch release data. Check if the repo exists and has releases.")
else:
    releases = response.json()
    downloads_data = []

    for release in releases:
        tag = release["tag_name"]
        for asset in release["assets"]:
            downloads_data.append({
                "Release": tag,
                "Asset": asset["name"],
                "Downloads": asset["download_count"],
                "Uploaded": asset["created_at"][:10]
            })

    if not downloads_data:
        st.warning("⚠️ No assets with downloads found. Please upload files in a release.")
    else:
        df = pd.DataFrame(downloads_data)
        st.dataframe(df)

        fig = px.bar(df, x="Asset", y="Downloads", color="Release",
                     title="GitHub Asset Downloads per Release",
                     labels={"Downloads": "Download Count"},
                     text="Downloads")
        st.plotly_chart(fig, use_container_width=True)
