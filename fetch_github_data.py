import os
import requests
import pandas as pd

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"

def fetch_pull_requests(owner, repo):
    pr_counts = {}
    page = 1
    while True:
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls?state=all&per_page=100&page={page}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print(f"❌ Error fetching PRs: {response.status_code} {response.text}")
            return None
        prs = response.json()
        if not prs:
            break
        for pr in prs:
            date = pr['created_at'][:10]
            pr_counts[date] = pr_counts.get(date, 0) + 1
        page += 1
    # Convert dict to dataframe
    df = pd.DataFrame(list(pr_counts.items()), columns=['date', 'pr_count'])
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df

def fetch_pypi_downloads(package_name):
    url = f"https://pypistats.org/api/packages/{package_name}/recent"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Error fetching PyPI downloads: {response.status_code} {response.text}")
        return None
    data = response.json()
    downloads = data.get('data', [])
    # Extract daily downloads
    df = pd.DataFrame(downloads)
    if df.empty:
        print("⚠️ No download data found.")
        return None
    df['date'] = pd.to_datetime(df['date'])
    df = df[['date', 'downloads']].sort_values('date').reset_index(drop=True)
    return df

def save_csv(df, filename):
    df.to_csv(filename, index=False)
    print(f"✅ Saved {filename}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python fetch_github_data.py owner repo")
        exit(1)

    owner, repo = sys.argv[1], sys.argv[2]

    print(f"🔁 Fetching pull requests for {owner}/{repo}...")
    pr_df = fetch_pull_requests(owner, repo)
    if pr_df is not None:
        save_csv(pr_df, "data/github_pull_requests.csv")

    print(f"�� Fetching PyPI downloads for {repo}...")
    downloads_df = fetch_pypi_downloads(repo)
    if downloads_df is not None:
        save_csv(downloads_df, "data/github_downloads.csv")

