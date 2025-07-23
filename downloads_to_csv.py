import requests
import pandas as pd

package = "pandas"  # Change this to your PyPI package name
url = f"https://pypistats.org/api/packages/{package}/overall"

print("Fetching download data from PyPIStats...")
response = requests.get(url)

if response.status_code != 200:
    raise Exception(f"Failed to fetch data. Status: {response.status_code}")

data = response.json()["data"]

# Convert to DataFrame
df = pd.DataFrame(data)
df["date"] = pd.to_datetime(df["date"])
df = df[df["category"] == "with_mirrors"]  # Filter to include all downloads
df.rename(columns={"downloads": "downloads"}, inplace=True)
df = df[["date", "downloads"]].sort_values("date")

# Save to CSV
df.to_csv("data/github_downloads.csv", index=False)
print("✅ Downloads saved to: data/github_downloads.csv")
