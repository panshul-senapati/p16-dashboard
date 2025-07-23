import requests
import pandas as pd
import os

def fetch_pypi_downloads(package_name):
    print(f"�� Fetching PyPI downloads for {package_name}...")
    url = f"https://pypistats.org/api/packages/{package_name}/recent"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Error fetching PyPI downloads: {response.status_code} {response.text}")
        return None

    data = response.json()
    downloads = data.get('data')
    if not downloads or not isinstance(downloads, list):
        print(f"⚠️ Unexpected or empty downloads data for {package_name}: {downloads}")
        return None

    df = pd.DataFrame(downloads)
    df['date'] = pd.to_datetime(df['date'])
    df = df[['date', 'downloads']].sort_values('date').reset_index(drop=True)
    return df

def save_csv(df, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    df.to_csv(filename, index=False)
    print(f"✅ Saved {filename}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python fetch_pypi_downloads.py package_name")
        exit(1)

    package_name = sys.argv[1]
    df = fetch_pypi_downloads(package_name)
    if df is not None:
        save_csv(df, f"data/pypi_downloads_{package_name}.csv")

