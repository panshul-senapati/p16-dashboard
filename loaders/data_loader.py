import os
from typing import Optional

import pandas as pd


class DataLoader:
    """Loads metric CSVs produced by fetchers into pandas DataFrames."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

    def _path_for(self, data_type: str) -> str:
        mapping = {
            "stars": "github_stars.csv",
            "forks": "github_forks.csv",
            "prs": "github_pull_requests.csv",
            "downloads": "github_downloads.csv",
        }
        fname = mapping.get(data_type)
        if not fname:
            raise ValueError(f"Unknown data_type: {data_type}")
        return os.path.join(self.data_dir, fname)

    def get(self, data_type: str) -> pd.DataFrame:
        path = self._path_for(data_type)
        if not os.path.exists(path):
            # Return empty DF with correct schema
            columns = {
                "stars": ["date", "stars"],
                "forks": ["date", "forks"],
                "prs": ["date", "pr_count"],
                "downloads": ["date", "downloads"],
            }[data_type]
            return pd.DataFrame(columns=columns)

        df = pd.read_csv(path)
        # Ensure expected columns exist
        expected = {
            "stars": {"date", "stars"},
            "forks": {"date", "forks"},
            "prs": {"date", "pr_count"},
            "downloads": {"date", "downloads"},
        }[data_type]
        if not expected.issubset(set(df.columns)):
            return pd.DataFrame(columns=list(expected))

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        return df


