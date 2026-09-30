"""Thin client for the FRED/ALFRED API.

ALFRED exposes every historical vintage of a series through the regular
FRED observations endpoint when you pass a wide real-time window.
Each returned row says: "for this observation date, this value was the
published number from realtime_start through realtime_end."
"""
import os
import time

import requests

BASE_URL = "https://api.stlouisfed.org/fred"
REALTIME_MIN = "1776-07-04"   # earliest real-time date FRED accepts
REALTIME_MAX = "9999-12-31"   # FRED's marker for "still current"
PAGE_LIMIT = 100_000          # FRED's max rows per request


class FredClient:
    def __init__(self, api_key=None, session=None, max_retries=4):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "No FRED API key found. Get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html and set FRED_API_KEY."
            )
        self.session = session or requests.Session()
        self.max_retries = max_retries

    def _get(self, endpoint, **params):
        params.update(api_key=self.api_key, file_type="json")
        url = f"{BASE_URL}/{endpoint}"
        for attempt in range(self.max_retries):
            resp = self.session.get(url, params=params, timeout=60)
            # Back off on rate limits and server errors, fail fast on everything else
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        raise RuntimeError(f"Request to {endpoint} failed after {self.max_retries} attempts")

    def series_info(self, series_id):
        """Metadata for the series: title, units, frequency, seasonal adjustment, notes."""
        return self._get("series", series_id=series_id)["seriess"][0]

    def all_vintages(self, series_id, observation_start="1900-01-01"):
        """Every published value of every observation, with its real-time validity window."""
        rows, offset = [], 0
        while True:
            data = self._get(
                "series/observations",
                series_id=series_id,
                realtime_start=REALTIME_MIN,
                realtime_end=REALTIME_MAX,
                observation_start=observation_start,
                sort_order="asc",
                limit=PAGE_LIMIT,
                offset=offset,
            )
            batch = data["observations"]
            rows.extend(batch)
            if len(batch) < PAGE_LIMIT:
                return rows
            offset += PAGE_LIMIT
