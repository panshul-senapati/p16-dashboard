import requests
import json

package = "pandas"
url = f"https://pypistats.org/api/packages/{package}/recent"

headers = {
    "Accept": "application/json",
    "User-Agent": "p16-dashboard"
}

r = requests.get(url, headers=headers)
print(f"Status code: {r.status_code}")

if r.status_code == 200:
    print("✅ Successfully fetched PyPI stats")
    print(json.dumps(r.json(), indent=2))  # <-- This shows the full JSON response
else:
    print("❌ Failed to fetch PyPI stats")
