"""SQLite storage for series metadata and vintage rows.

Schema design:
  series    one row per series, the metadata catalog
  vintages  one row per (observation date, real-time window), the full revision history

Keying vintages on (series_id, obs_date, realtime_start) makes every published
value addressable, and the real-time index makes "as of date X" queries cheap.
"""
import sqlite3
from datetime import datetime, timezone

import pandas as pd

from .fredapi import REALTIME_MAX

SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    series_id           TEXT PRIMARY KEY,
    title               TEXT,
    units               TEXT,
    frequency           TEXT,
    seasonal_adjustment TEXT,
    source_last_updated TEXT,
    notes               TEXT,
    fetched_at          TEXT
);
CREATE TABLE IF NOT EXISTS vintages (
    series_id      TEXT NOT NULL,
    obs_date       TEXT NOT NULL,
    realtime_start TEXT NOT NULL,
    realtime_end   TEXT NOT NULL,
    value          REAL,            -- NULL where FRED published '.' (missing)
    PRIMARY KEY (series_id, obs_date, realtime_start)
);
CREATE INDEX IF NOT EXISTS idx_vintages_realtime
    ON vintages (series_id, realtime_start, realtime_end);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def save_series(conn, info):
    conn.execute(
        "INSERT OR REPLACE INTO series VALUES (?,?,?,?,?,?,?,?)",
        (
            info["id"], info.get("title"), info.get("units"), info.get("frequency"),
            info.get("seasonal_adjustment"), info.get("last_updated"), info.get("notes"),
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )
    conn.commit()


def _to_float(v):
    return None if v in (".", "", None) else float(v)


def save_vintages(conn, series_id, rows):
    """Replace the stored history for a series in one transaction, so reruns are idempotent."""
    with conn:
        conn.execute("DELETE FROM vintages WHERE series_id = ?", (series_id,))
        conn.executemany(
            "INSERT INTO vintages VALUES (?,?,?,?,?)",
            [(series_id, r["date"], r["realtime_start"], r["realtime_end"], _to_float(r["value"]))
             for r in rows],
        )


def load_series(conn, series_id):
    cur = conn.execute("SELECT * FROM series WHERE series_id = ?", (series_id,))
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip([c[0] for c in cur.description], row))


def load_vintages(conn, series_id):
    df = pd.read_sql_query(
        "SELECT obs_date, realtime_start, realtime_end, value FROM vintages WHERE series_id = ?",
        conn, params=(series_id,),
    )
    return prepare(df)


def prepare(df):
    """Parse dates. The open-ended marker 9999-12-31 becomes NaT, meaning 'still current'."""
    df = df.copy()
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    df["realtime_start"] = pd.to_datetime(df["realtime_start"])
    end = df["realtime_end"].astype(str)
    df["realtime_end"] = pd.to_datetime(end.where(end != REALTIME_MAX))
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.sort_values(["obs_date", "realtime_start"]).reset_index(drop=True)
