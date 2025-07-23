from github import Github
import pandas as pd
from collections import Counter
import os
from dotenv import load_dotenv

# Load token from .env file if available
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Or replace with your token string

if not GITHUB_TOKEN:
    raise ValueError("GitHub token not found. Set it in .env or hardcode it.")

# Repo info
owner = "pandas-dev"   # Change this to your repo owner
repo_name = "pandas"   # Change this to your repo name

g = Github(GITHUB_TOKEN)
repo = g.get_repo(f"{owner}/{repo_name}")
pulls = repo.get_pulls(state="all", sort="created", direction="asc")

pr_dates = []
print("Fetching pull requests...")

# Fetch all pull requests (paginated)
for pr in pulls:
    pr_dates.append(pr.created_at.date())

# Count PRs per day
counter = Counter(pr_dates)
df_pr = pd.DataFrame(counter.items(), columns=["date", "pr_count"]).sort_values("date")
df_pr["date"] = pd.to_datetime(df_pr["date"])

# Save to CSV
df_pr.to_csv("data/github_pull_requests.csv", index=False)
print("✅ Pull requests saved to: data/github_pull_requests.csv")

