import requests

package = "pandas"
url = f"https://pypi.org/pypi/{package}/json"

r = requests.get(url)
print(f"Status code: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    print("Package name:", data["info"]["name"])
    print("Latest version:", data["info"]["version"])
else:
    print("❌ Failed to fetch release info")
