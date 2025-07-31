import requests

# Replace with your repo info
username = "panshul-senapati"
repo = "p16-dashboard"
url = f"https://api.github.com/repos/{username}/{repo}/releases"

response = requests.get(url)
data = response.json()

for release in data:
    print(f"📦 Release: {release['tag_name']}")
    for asset in release['assets']:
        print(f"  └── {asset['name']} → {asset['download_count']} downloads")
