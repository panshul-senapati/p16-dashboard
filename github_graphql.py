import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # Load .env file (make sure GITHUB_TOKEN is in .env)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not found in environment variables. Please set it in your .env file.")

HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
GRAPHQL_URL = "https://api.github.com/graphql"

def run_query(query, variables=None):
    json = {'query': query}
    if variables:
        json['variables'] = variables
    response = requests.post(GRAPHQL_URL, json=json, headers=HEADERS)
    if response.status_code != 200:
        raise Exception(f"Query failed with status code {response.status_code}: {response.text}")
    return response.json()

def fetch_stargazers(owner, repo):
    query = """
    query($owner:String!, $name:String!, $cursor:String){
      repository(owner:$owner, name:$name) {
        stargazers(first: 100, after: $cursor) {
          pageInfo {
            hasNextPage
            endCursor
          }
          edges {
            starredAt
          }
        }
      }
    }
    """
    stars = []
    cursor = None
    while True:
        variables = {"owner": owner, "name": repo, "cursor": cursor}
        result = run_query(query, variables)
        edges = result["data"]["repository"]["stargazers"]["edges"]
        for edge in edges:
            stars.append(edge["starredAt"][:10])  # YYYY-MM-DD
        page_info = result["data"]["repository"]["stargazers"]["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]
    df = pd.DataFrame(stars, columns=["date"])
    df['count'] = 1
    df = df.groupby("date").count().reset_index().sort_values("date")
    df['stars'] = df['count'].cumsum()
    df.drop(columns=['count'], inplace=True)
    return df

def fetch_forks(owner, repo):
    query = """
    query($owner:String!, $name:String!, $cursor:String){
      repository(owner:$owner, name:$name) {
        forks(first: 100, after: $cursor) {
          pageInfo {
            hasNextPage
            endCursor
          } 
          edges {
            node {
              createdAt
            }
          }
        }
      }
    }
    """
    forks = []
    cursor = None
    while True:
        variables = {"owner": owner, "name": repo, "cursor": cursor}
        result = run_query(query, variables)
        edges = result["data"]["repository"]["forks"]["edges"]
        for edge in edges:
            forks.append(edge["node"]["createdAt"][:10])
        page_info = result["data"]["repository"]["forks"]["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]
    df = pd.DataFrame(forks, columns=["date"])
    df['count'] = 1
    df = df.groupby("date").count().reset_index().sort_values("date")
    df['forks'] = df['count'].cumsum()
    df.drop(columns=['count'], inplace=True)
    return df

def save_csv(df, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    df.to_csv(filename, index=False)
    print(f"Saved {filename}")

def load_csv(filename):
    if os.path.exists(filename):
        return pd.read_csv(filename, parse_dates=['date'])
    else:
        return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python github_graphql.py owner repo")
        exit(1)

    owner, repo = sys.argv[1], sys.argv[2]

    print(f"Fetching stars for {owner}/{repo}...")
    stars_df = fetch_stargazers(owner, repo)
    save_csv(stars_df, "data/github_stars.csv")

    print(f"Fetching forks for {owner}/{repo}...")
    forks_df = fetch_forks(owner, repo)
    save_csv(forks_df, "data/github_forks.csv")
