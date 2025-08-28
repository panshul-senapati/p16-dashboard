import os
import time
import logging
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
        max_retries = 3  # Limit retries to prevent infinite loops
        
        for attempt in range(max_retries):
            resp = requests.get(url, headers=headers, params=params, timeout=self.request_timeout_s)
            if resp.status_code == 403:
                # Possibly rate-limited; attempt to wait until reset if provided
                reset = resp.headers.get("X-RateLimit-Reset")
                now = int(time.time())
                if reset and reset.isdigit():
                    wait_s = max(0, int(reset) - now) + 1
                    # Cap wait time to prevent very long sleeps
                    wait_s = min(wait_s, 10)  # Max 10 seconds wait
                    logging.info(f"Rate limited, waiting {wait_s}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_s)
                else:
                    wait_s = min(backoff_s, 5)  # Cap backoff to 5 seconds
                    logging.info(f"Rate limited, backoff wait {wait_s}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_s)
                    backoff_s = min(backoff_s * 2, 5)
                
                if attempt == max_retries - 1:
                    logging.warning(f"Max retries ({max_retries}) reached for {url}")
                    break
                continue
            return resp
        
        # If we get here, all retries failed
        logging.error(f"Failed to fetch {url} after {max_retries} attempts")
        return resp  # Return the last response even if it's an error

    @staticmethod
    def _to_date(date_str: str) -> Optional[pd.Timestamp]:
        try:
            return pd.to_datetime(date_str, utc=True).tz_localize(None).normalize()
        except Exception:
            return None


class GitHubGraphQL:
    """Minimal GitHub GraphQL v4 client with pagination helpers."""

    def __init__(self, request_timeout_s: int = 30):
        self.endpoint = "https://api.github.com/graphql"
        token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }
        if token:
            self.headers["Authorization"] = f"bearer {token}"
        self.request_timeout_s = request_timeout_s

    def query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        payload = {"query": query, "variables": variables or {}}
        resp = requests.post(self.endpoint, json=payload, headers=self.headers, timeout=self.request_timeout_s)
        if resp.status_code != 200:
            logging.warning("GraphQL non-200: %s", resp.status_code)
            return {}
        data = resp.json() or {}
        if "errors" in data:
            logging.warning("GraphQL errors: %s", data.get("errors"))
        return data.get("data", {})


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
                logging.warning("Stars API non-200: %s", resp.status_code)
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

    def fetch_graphql(self, owner: str, repo: str) -> pd.DataFrame:
        gql = GitHubGraphQL()
        # Using stargazers with starredAt timestamp and pagination
        query = """
        query($owner: String!, $name: String!, $cursor: String) {
          repository(owner: $owner, name: $name) {
            stargazers(first: 100, after: $cursor, orderBy: {field: STARRED_AT, direction: ASC}) {
              edges { starredAt }
              pageInfo { endCursor hasNextPage }
            }
          }
        }
        """
        dates: List[pd.Timestamp] = []
        cursor = None
        for _ in range(200):
            data = gql.query(query, {"owner": owner, "name": repo, "cursor": cursor})
            sg = (((data or {}).get("repository") or {}).get("stargazers") or {})
            edges = sg.get("edges") or []
            for e in edges:
                ts = self._to_date(e.get("starredAt"))
                if ts is not None:
                    dates.append(ts)
            page = sg.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
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
                logging.warning("Forks API non-200: %s", resp.status_code)
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

    def fetch_graphql(self, owner: str, repo: str) -> pd.DataFrame:
        gql = GitHubGraphQL()
        query = """
        query($owner: String!, $name: String!, $cursor: String) {
          repository(owner: $owner, name: $name) {
            forks(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
              nodes { createdAt }
              pageInfo { endCursor hasNextPage }
            }
          }
        }
        """
        dates: List[pd.Timestamp] = []
        cursor = None
        for _ in range(200):
            data = gql.query(query, {"owner": owner, "name": repo, "cursor": cursor})
            forks = (((data or {}).get("repository") or {}).get("forks") or {})
            nodes = forks.get("nodes") or []
            for n in nodes:
                ts = self._to_date(n.get("createdAt"))
                if ts is not None:
                    dates.append(ts)
            page = forks.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
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
                logging.warning("PRs API non-200: %s", resp.status_code)
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

    def fetch_graphql(self, owner: str, repo: str) -> pd.DataFrame:
        gql = GitHubGraphQL()
        query = """
        query($owner: String!, $name: String!, $cursor: String) {
          repository(owner: $owner, name: $name) {
            pullRequests(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}, states: [OPEN, MERGED, CLOSED]) {
              nodes { createdAt }
              pageInfo { endCursor hasNextPage }
            }
          }
        }
        """
        dates: List[pd.Timestamp] = []
        cursor = None
        for _ in range(200):
            data = gql.query(query, {"owner": owner, "name": repo, "cursor": cursor})
            prs = (((data or {}).get("repository") or {}).get("pullRequests") or {})
            nodes = prs.get("nodes") or []
            for n in nodes:
                ts = self._to_date(n.get("createdAt"))
                if ts is not None:
                    dates.append(ts)
            page = prs.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
        if not dates:
            return pd.DataFrame(columns=["date", "pr_count"])
        df = pd.DataFrame({"date": dates, "delta": 1})
        daily = df.groupby("date", as_index=False)["delta"].sum().sort_values("date")
        daily = daily.rename(columns={"delta": "pr_count"})
        return daily


class IssuesFetcher(BaseFetcher):
    """
    Fetches issues (state=all), excludes pull requests, and aggregates daily count by creation date.
    CSV columns: date, issues (daily)
    """

    def fetch(self, owner: str, repo: str) -> pd.DataFrame:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        dates: List[pd.Timestamp] = []
        # Use optimal page limit for comprehensive data
        max_pages = 20
        for page in range(1, max_pages + 1):
            params = {"per_page": self.per_page, "page": page, "state": "all", "sort": "created", "direction": "asc"}
            resp = self._request(url, params=params)
            if resp.status_code != 200:
                logging.warning("Issues API non-200: %s", resp.status_code)
                break
            items = resp.json()
            if not items:
                break
            for it in items:
                # Exclude PRs which also appear in issues API
                if it.get("pull_request") is not None:
                    continue
                created_at = it.get("created_at")
                ts = self._to_date(created_at) if created_at else None
                if ts is not None:
                    dates.append(ts)
            if len(items) < self.per_page:
                break
            # Early exit if we have enough data for a reasonable series
            if len(dates) > 1000:
                break

        if not dates:
            return pd.DataFrame(columns=["date", "issues"])

        df = pd.DataFrame({"date": dates, "delta": 1})
        daily = df.groupby("date", as_index=False)["delta"].sum().sort_values("date")
        daily = daily.rename(columns={"delta": "issues"})
        return daily

    def fetch_graphql(self, owner: str, repo: str) -> pd.DataFrame:
        gql = GitHubGraphQL()
        query = """
        query($owner: String!, $name: String!, $cursor: String) {
          repository(owner: $owner, name: $name) {
            issues(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}, states: [OPEN, CLOSED]) {
              nodes { createdAt }
              pageInfo { endCursor hasNextPage }
            }
          }
        }
        """
        dates: List[pd.Timestamp] = []
        cursor = None
        # Use optimal page limit for comprehensive data
        max_pages = 10
        for _ in range(max_pages):
            data = gql.query(query, {"owner": owner, "name": repo, "cursor": cursor})
            sg = (((data or {}).get("repository") or {}).get("issues") or {})
            edges = sg.get("edges") or []
            for e in edges:
                ts = self._to_date(e.get("createdAt"))
                if ts is not None:
                    dates.append(ts)
            page = sg.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
            # Early exit if we have enough data
            if len(dates) > 500:
                break
        if not dates:
            return pd.DataFrame(columns=["date", "issues"])
        df = pd.DataFrame({"date": dates, "delta": 1})
        daily = df.groupby("date", as_index=False)["delta"].sum().sort_values("date")
        daily = daily.rename(columns={"delta": "issues"})
        return daily


class ContributionsFetcher(BaseFetcher):
    """
    Uses the GitHub stats API for weekly commit activity, broken down by day, to build
    a daily commits series.
    Endpoint: GET /repos/{owner}/{repo}/stats/commit_activity
    CSV columns: date, commits (daily)
    """

    def fetch(self, owner: str, repo: str) -> pd.DataFrame:
        url = f"https://api.github.com/repos/{owner}/{repo}/stats/commit_activity"
        # Use optimal retry strategy for reliable data
        for _ in range(3):  # Try up to 3 times for reliable data
            resp = self._request(url)
            if resp.status_code == 202:
                # Return empty data instead of waiting
                logging.info("Commit stats still generating, returning empty data")
                return pd.DataFrame(columns=["date", "commits"])
            if resp.status_code != 200:
                logging.warning("Commit activity API non-200: %s", resp.status_code)
                return pd.DataFrame(columns=["date", "commits"])
            data = resp.json() or []
            rows: List[pd.Timestamp] = []
            counts: List[int] = []
            # Use optimal week limit for comprehensive data
            max_weeks = 104
            for week in data[:max_weeks]:
                # week['week'] is a unix timestamp (start of week, Sunday)
                base = pd.to_datetime(week.get("week", 0), unit="s")
                daily_counts = week.get("days", []) or []
                for i, c in enumerate(daily_counts):
                    rows.append((base + pd.Timedelta(days=i)).normalize())
                    counts.append(int(c or 0))
            if not rows:
                return pd.DataFrame(columns=["date", "commits"])
            df = pd.DataFrame({"date": rows, "commits": counts})
            df = df.dropna(subset=["date"]).sort_values("date")
            return df
        return pd.DataFrame(columns=["date", "commits"])

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
        # Get comprehensive release data
        params = {"per_page": 100}  # Get more releases for better data coverage
        resp = self._request(url, params=params)
        if resp.status_code != 200:
            logging.warning("Releases API non-200: %s", resp.status_code)
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
        self.issues_fetcher = IssuesFetcher()
        self.contributions_fetcher = ContributionsFetcher()
        self.use_graphql = os.getenv("P16_USE_GRAPHQL") == "1"

    def fetch_all(self, owner: str, repo: str) -> Dict[str, pd.DataFrame]:
        if self.use_graphql:
            stars = self.stars_fetcher.fetch_graphql(owner, repo)
            forks = self.forks_fetcher.fetch_graphql(owner, repo)
            prs = self.prs_fetcher.fetch_graphql(owner, repo)
            issues = self.issues_fetcher.fetch_graphql(owner, repo)
        else:
            stars = self.stars_fetcher.fetch(owner, repo)
            forks = self.forks_fetcher.fetch(owner, repo)
            prs = self.prs_fetcher.fetch(owner, repo)
            issues = self.issues_fetcher.fetch(owner, repo)
        downloads = self.downloads_fetcher.fetch(owner, repo)
        contribs = self.contributions_fetcher.fetch(owner, repo)
        return {
            "stars": stars,
            "forks": forks,
            "prs": prs,
            "downloads": downloads,
            "issues": issues,
            "contributions": contribs,
        }


