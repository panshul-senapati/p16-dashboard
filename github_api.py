import os
import datetime
import pandas as pd
from github import Github
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
g = Github(GITHUB_TOKEN)

def load_historic_data():
    stars_path = "data/github_stars.csv"
    forks_path = "data/github_forks.csv"

    stars_df = pd.read_csv(stars_path, parse_dates=["date"]) if os.path.exists(stars_path) else pd.DataFrame()
    forks_df = pd.read_csv(forks_path, parse_dates=["date"]) if os.path.exists(forks_path) else pd.DataFrame()

    return stars_df, forks_df

def fetch_daily_metrics(owner, repo_name):
    repo = g.get_repo(f"{owner}/{repo_name}")

    today = datetime.datetime.utcnow().date()

    # Example: fetch commits, issues, contributors as snapshot for today only
    commits = repo.get_commits(since=datetime.datetime(today.year, today.month, today.day)).totalCount
    open_issues = repo.open_issues_count
    contributors = repo.get_contributors().totalCount

    return {
        "date": today,
        "commits": commits,
        "open_issues": open_issues,
        "contributors": contributors,
    }

def save_daily_metrics(metrics, filename="data/github_daily_metrics.csv"):
    if os.path.exists(filename):
        df = pd.read_csv(filename, parse_dates=["date"])
    else:
        df = pd.DataFrame()

    new_row = pd.DataFrame([metrics])
    df = pd.concat([df, new_row], ignore_index=True)

    # Remove duplicates on date
    df = df.drop_duplicates(subset=["date"], keep="last")

    df.to_csv(filename, index=False)
    print(f"Saved daily metrics to {filename}")

def load_daily_metrics(filename="data/github_daily_metrics.csv"):
    if os.path.exists(filename):
        return pd.read_csv(filename, parse_dates=["date"])
    else:
        return pd.DataFrame()

if __name__ == "__main__":
    owner, repo = "pandas-dev", "pandas"

    # Load historic data
    stars_df, forks_df = load_historic_data()
    print("Historic stars:", stars_df.tail())
    print("Historic forks:", forks_df.tail())

    # Fetch daily snapshot and save
    daily_metrics = fetch_daily_metrics(owner, repo)
    print("Today's daily metrics:", daily_metrics)
    save_daily_metrics(daily_metrics)
 