import os
import time
import logging
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

        self.types = ["stars", "forks", "prs", "downloads", "issues", "contributions"]

    def _is_data_stale(self, path: str) -> bool:
        if not os.path.exists(path):
            return True
        mtime = os.path.getmtime(path)
        age_hours = (time.time() - mtime) / 3600.0
        return age_hours > self.refresh_threshold_hours

    def _fetch_and_save_data(self, data_type: str, owner: str, repo: str) -> pd.DataFrame:
        if data_type == "stars":
            df = self.fetcher.stars_fetcher.fetch(owner, repo)
        elif data_type == "forks":
            df = self.fetcher.forks_fetcher.fetch(owner, repo)
        elif data_type == "prs":
            df = self.fetcher.prs_fetcher.fetch(owner, repo)
        elif data_type == "downloads":
            df = self.fetcher.downloads_fetcher.fetch(owner, repo)
        elif data_type == "issues":
            df = self.fetcher.issues_fetcher.fetch(owner, repo)
        elif data_type == "contributions":
            df = self.fetcher.contributions_fetcher.fetch(owner, repo)
        else:
            raise ValueError(f"Unknown data_type: {data_type}")

        # Ensure columns are as expected and save
        expected_cols = {
            "stars": ["date", "stars"],
            "forks": ["date", "forks"],
            "prs": ["date", "pr_count"],
            "downloads": ["date", "downloads"],
            "issues": ["date", "issues"],
            "contributions": ["date", "commits"],
        }[data_type]
        df = df[[c for c in expected_cols if c in df.columns]]
        try:
            out_path = self.loader.path_for(data_type, owner, repo)
            df.to_csv(out_path, index=False)
        except Exception as e:
            logging.error("Failed to write CSV for %s: %s", data_type, e)
        return df

    def _load_data(self, data_type: str, owner: str, repo: str) -> pd.DataFrame:
        return self.loader.get_for(data_type, owner, repo)

    def get_data(self, data_type: str, owner: str, repo: str, force_refresh: bool = False) -> pd.DataFrame:
        path = self.loader.path_for(data_type, owner, repo)
        if force_refresh or self._is_data_stale(path):
            logging.info("Fetching fresh data for %s/%s %s (force_refresh=%s)", owner, repo, data_type, force_refresh)
            return self._fetch_and_save_data(data_type, owner, repo)
        logging.info("Loading cached data for %s/%s %s", owner, repo, data_type)
        return self._load_data(data_type, owner, repo)

    def get_all_cached_data(self, owner: str, repo: str, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        types_to_process = self.types
        return {t: self.get_data(t, owner, repo, force_refresh=force_refresh) for t in types_to_process}

    def get_all_cached_data_for_range(self, owner: str, repo: str, start_date, end_date, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        """
        Smart range-aware retrieval that only fetches missing data.
        - If no cache: fetch full series and save.
        - If force_refresh: fetch fresh data for all types.
        - Else check if cached data covers the requested range and only fetch what's missing.
        """
        result: Dict[str, pd.DataFrame] = {}
        types_to_process = self.types
        
        for t in types_to_process:
            path = self.loader.path_for(t, owner, repo)
            cached = self._load_data(t, owner, repo) if os.path.exists(path) else pd.DataFrame(columns={
                "stars": ["date", "stars"],
                "forks": ["date", "forks"],
                "prs": ["date", "pr_count"],
                "downloads": ["date", "downloads"],
                "issues": ["date", "issues"],
                "contributions": ["date", "commits"],
            }[t])

            need_fetch = force_refresh or cached.empty

            if not need_fetch and not cached.empty:
                # Check if cached data covers the requested range
                try:
                    cached_dates = pd.to_datetime(cached["date"])
                    req_start = pd.to_datetime(start_date)
                    req_end = pd.to_datetime(end_date)
                    
                    # Check if we have data covering the entire requested range
                    range_covered = (
                        cached_dates.min() <= req_start and 
                        cached_dates.max() >= req_end and 
                        not self._is_data_stale(path)
                    )
                    
                    if not range_covered:
                        logging.info(f"Data for {t} doesn't cover requested range {start_date} to {end_date}, fetching fresh data")
                        need_fetch = True
                except Exception as e:
                    logging.warning(f"Error checking date coverage for {t}: {e}, will fetch fresh data")
                    need_fetch = True

            if need_fetch:
                logging.info(f"Fetching fresh data for {t}")
                fresh = self._fetch_and_save_data(t, owner, repo)
                if cached.empty:
                    merged = fresh
                else:
                    # Merge cached and fresh data, removing duplicates
                    merged = pd.concat([cached, fresh], ignore_index=True)
                    merged = merged.drop_duplicates(subset=["date"]).sort_values("date")
                
                # Persist merged data
                try:
                    merged.to_csv(path, index=False)
                except Exception as e:
                    logging.error("Failed to persist merged CSV for %s: %s", t, e)
                
                result[t] = merged
            else:
                logging.info(f"Using cached data for {t}")
                result[t] = cached

        return result

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


