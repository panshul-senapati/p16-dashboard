import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests


class BaseFetcher:
    """
    Shared HTTP logic for GitHub API access with optional authentication and
    simple rate limit handling (sleep-and-retry on 403 due to rate limit).
    """

    def __init__(self, per_page: int = 100, max_pages: int = 1000, request_timeout_s: int = 30):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github+json",
        }
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"
        self.per_page = per_page
        self.max_pages = max_pages
        self.request_timeout_s = request_timeout_s

    def _request(self, url: str, params: Optional[Dict] = None, extra_headers: Optional[Dict] = None) -> requests.Response:
        headers = dict(self.headers)
        if extra_headers:
            headers.update(extra_headers)

        backoff_s = 2
        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=self.request_timeout_s)
            if resp.status_code == 403:
                # Possibly rate-limited; attempt to wait until reset if provided
                reset = resp.headers.get("X-RateLimit-Reset")
                now = int(time.time())
                if reset and reset.isdigit():
                    wait_s = max(0, int(reset) - now) + 1
                    time.sleep(min(wait_s, 60))  # cap wait to 60s to avoid very long sleeps
                else:
                    time.sleep(backoff_s)
                    backoff_s = min(backoff_s * 2, 60)
                continue
            return resp

    @staticmethod
    def _to_date(date_str: str) -> Optional[pd.Timestamp]:
        try:
            return pd.to_datetime(date_str, utc=True).tz_localize(None).normalize()
        except Exception:
            return None


class StarsFetcher(BaseFetcher):
    """
    Fetches stargazer events with timestamps and returns cumulative stars by date.
    CSV columns: date, stars (cumulative total)
    """

    def fetch(self, owner: str, repo: str) -> pd.DataFrame:
        url = f"https://api.github.com/repos/{owner}/{repo}/stargazers"
        # To get timestamps, GitHub requires a specific Accept header
        extra_headers = {"Accept": "application/vnd.github.v3.star+json"}

        dates: List[pd.Timestamp] = []
        for page in range(1, self.max_pages + 1):
            params = {"per_page": self.per_page, "page": page}
            resp = self._request(url, params=params, extra_headers=extra_headers)
            if resp.status_code != 200:
                break
            items = resp.json()
            if not items:
                break
            for it in items:
                starred_at = it.get("starred_at")
                ts = self._to_date(starred_at) if starred_at else None
                if ts is not None:
                    dates.append(ts)
            if len(items) < self.per_page:
                break

        if not dates:
            return pd.DataFrame(columns=["date", "stars"])

        df = pd.DataFrame({"date": dates, "delta": 1})
        daily = df.groupby("date", as_index=False)["delta"].sum().sort_values("date")
        daily["stars"] = daily["delta"].cumsum()
        return daily[["date", "stars"]]


class ForksFetcher(BaseFetcher):
    """
    Fetches forks and aggregates to cumulative forks by fork creation date.
    CSV columns: date, forks (cumulative total)
    """

    def fetch(self, owner: str, repo: str) -> pd.DataFrame:
        url = f"https://api.github.com/repos/{owner}/{repo}/forks"
        dates: List[pd.Timestamp] = []
        for page in range(1, self.max_pages + 1):
            params = {"per_page": self.per_page, "page": page, "sort": "newest"}
            resp = self._request(url, params=params)
            if resp.status_code != 200:
                break
            items = resp.json()
            if not items:
                break
            for it in items:
                created_at = it.get("created_at")
                ts = self._to_date(created_at) if created_at else None
                if ts is not None:
                    dates.append(ts)
            if len(items) < self.per_page:
                break

        if not dates:
            return pd.DataFrame(columns=["date", "forks"])

        df = pd.DataFrame({"date": dates, "delta": 1})
        daily = df.groupby("date", as_index=False)["delta"].sum().sort_values("date")
        daily["forks"] = daily["delta"].cumsum()
        return daily[["date", "forks"]]


class PRsFetcher(BaseFetcher):
    """
    Fetches pull requests (state=all) and aggregates daily count by creation date.
    CSV columns: date, pr_count (daily)
    """

    def fetch(self, owner: str, repo: str) -> pd.DataFrame:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        dates: List[pd.Timestamp] = []
        for page in range(1, self.max_pages + 1):
            params = {"per_page": self.per_page, "page": page, "state": "all", "sort": "created", "direction": "asc"}
            resp = self._request(url, params=params)
            if resp.status_code != 200:
                break
            items = resp.json()
            if not items:
                break
            for it in items:
                created_at = it.get("created_at")
                ts = self._to_date(created_at) if created_at else None
                if ts is not None:
                    dates.append(ts)
            if len(items) < self.per_page:
                break

        if not dates:
            return pd.DataFrame(columns=["date", "pr_count"])

        df = pd.DataFrame({"date": dates, "delta": 1})
        daily = df.groupby("date", as_index=False)["delta"].sum().sort_values("date")
        daily = daily.rename(columns={"delta": "pr_count"})
        return daily


class DownloadsFetcher(BaseFetcher):
    """
    Fetches release assets and approximates daily download counts.
    NOTE: GitHub's asset "download_count" is cumulative per asset; this
    implementation groups by asset upload date and sums current counts, which
    produces a non-decreasing series approximating cumulative downloads.
    CSV columns: date, downloads (cumulative)
    """

    def fetch(self, owner: str, repo: str) -> pd.DataFrame:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        resp = self._request(url)
        if resp.status_code != 200:
            return pd.DataFrame(columns=["date", "downloads"])
        releases = resp.json() or []
        rows: List[Tuple[Optional[pd.Timestamp], int]] = []
        for rel in releases:
            for asset in rel.get("assets", []):
                created = asset.get("created_at") or asset.get("updated_at")
                ts = self._to_date(created) if created else None
                count = int(asset.get("download_count", 0) or 0)
                rows.append((ts, count))

        if not rows:
            return pd.DataFrame(columns=["date", "downloads"])

        df = pd.DataFrame(rows, columns=["date", "count"]).dropna(subset=["date"]).sort_values("date")
        # Sum counts by date, then cumulative sum to approximate cumulative downloads
        daily = df.groupby("date", as_index=False)["count"].sum().sort_values("date")
        daily["downloads"] = daily["count"].cumsum()
        return daily[["date", "downloads"]]


class GitHubFetcher:
    """Aggregates all metric fetchers and exposes a single interface."""

    def __init__(self):
        self.stars_fetcher = StarsFetcher()
        self.forks_fetcher = ForksFetcher()
        self.prs_fetcher = PRsFetcher()
        self.downloads_fetcher = DownloadsFetcher()

    def fetch_all(self, owner: str, repo: str) -> Dict[str, pd.DataFrame]:
        return {
            "stars": self.stars_fetcher.fetch(owner, repo),
            "forks": self.forks_fetcher.fetch(owner, repo),
            "prs": self.prs_fetcher.fetch(owner, repo),
            "downloads": self.downloads_fetcher.fetch(owner, repo),
        }


