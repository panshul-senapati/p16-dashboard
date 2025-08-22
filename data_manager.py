import os
import time
from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

from fetchers.github_fetcher import GitHubFetcher
from loaders.data_loader import DataLoader


@dataclass
class DataFileInfo:
    path: str
    exists: bool
    age_hours: Optional[float]
    stale: bool


class DataManager:
    """
    Orchestrates fetching vs. loading, manages cache freshness, and exposes
    simple APIs for retrieving metric dataframes.
    """

    def __init__(self, data_dir: str = "data", refresh_threshold_hours: int = 24):
        self.data_dir = data_dir
        self.refresh_threshold_hours = refresh_threshold_hours
        os.makedirs(self.data_dir, exist_ok=True)

        self.fetcher = GitHubFetcher()
        self.loader = DataLoader(data_dir=self.data_dir)

        self.type_to_file = {
            "stars": os.path.join(self.data_dir, "github_stars.csv"),
            "forks": os.path.join(self.data_dir, "github_forks.csv"),
            "prs": os.path.join(self.data_dir, "github_pull_requests.csv"),
            "downloads": os.path.join(self.data_dir, "github_downloads.csv"),
        }

    def _is_data_stale(self, path: str) -> bool:
        if not os.path.exists(path):
            return True
        mtime = os.path.getmtime(path)
        age_hours = (time.time() - mtime) / 3600.0
        return age_hours > self.refresh_threshold_hours

    def _fetch_and_save_data(self, data_type: str, owner: str, repo: str) -> pd.DataFrame:
        df: pd.DataFrame
        if data_type == "stars":
            df = self.fetcher.stars_fetcher.fetch(owner, repo)
        elif data_type == "forks":
            df = self.fetcher.forks_fetcher.fetch(owner, repo)
        elif data_type == "prs":
            df = self.fetcher.prs_fetcher.fetch(owner, repo)
        elif data_type == "downloads":
            df = self.fetcher.downloads_fetcher.fetch(owner, repo)
        else:
            raise ValueError(f"Unknown data_type: {data_type}")

        # Ensure columns are as expected and save
        expected_cols = {
            "stars": ["date", "stars"],
            "forks": ["date", "forks"],
            "prs": ["date", "pr_count"],
            "downloads": ["date", "downloads"],
        }[data_type]
        df = df.loc[:, [c for c in expected_cols if c in df.columns]]
        df.to_csv(self.type_to_file[data_type], index=False)
        return df

    def _load_data(self, data_type: str) -> pd.DataFrame:
        return self.loader.get(data_type)

    def get_data(self, data_type: str, owner: str, repo: str, force_refresh: bool = False) -> pd.DataFrame:
        path = self.type_to_file[data_type]
        if force_refresh or self._is_data_stale(path):
            return self._fetch_and_save_data(data_type, owner, repo)
        return self._load_data(data_type)

    def get_all_cached_data(self, owner: str, repo: str, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        return {
            t: self.get_data(t, owner, repo, force_refresh=force_refresh)
            for t in self.type_to_file.keys()
        }

    def get_data_status(self) -> Dict[str, DataFileInfo]:
        status: Dict[str, DataFileInfo] = {}
        now = time.time()
        for t, path in self.type_to_file.items():
            exists = os.path.exists(path)
            if exists:
                age_hours = (now - os.path.getmtime(path)) / 3600.0
                stale = age_hours > self.refresh_threshold_hours
            else:
                age_hours = None
                stale = True
            status[t] = DataFileInfo(path=path, exists=exists, age_hours=age_hours, stale=stale)
        return status

    def clear_cache(self, data_type: Optional[str] = None) -> None:
        if data_type is None:
            for path in self.type_to_file.values():
                if os.path.exists(path):
                    os.remove(path)
        else:
            path = self.type_to_file.get(data_type)
            if path and os.path.exists(path):
                os.remove(path)


