import requests

def get_pypi_release_info(package_name):
    url = f"https://pypi.org/pypi/{package_name}/json"
    r = requests.get(url)
    if r.status_code != 200:
        return []
    data = r.json()
    releases = data.get("releases", {})

    release_list = []
    for version, files in releases.items():
        if files:
            upload_time = files[0].get("upload_time")
            release_list.append({"version": version, "upload_time": upload_time})

    release_list.sort(key=lambda x: x["upload_time"] or "", reverse=True)
    return release_list

def get_pypi_downloads(package_name):
    url = f"https://pypistats.org/api/packages/{package_name}/recent"
    headers = {
        "Accept": "application/json",
        "User-Agent": "p16-dashboard"
    }
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return []
    data = r.json().get("data", {})
    # Convert to list of dictionaries for consistency with chart format
    downloads = [
        {"date": "Last day", "downloads": data.get("last_day", 0)},
        {"date": "Last week", "downloads": data.get("last_week", 0)},
        {"date": "Last month", "downloads": data.get("last_month", 0)},
    ]
    return downloads

