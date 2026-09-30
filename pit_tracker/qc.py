"""Data quality checks on a vintage history.

Each check returns a list of findings: {check, severity, detail}.
Severity: 'error' means the data is structurally wrong, 'warning' means review it,
'info' means worth knowing (for example, a real structural break like 2020).
"""
from datetime import datetime

import pandas as pd

from .pointintime import latest, revision_table

FREQ_MAP = {"Monthly": "MS", "Quarterly": "QS", "Annual": "YS", "Weekly": "W", "Daily": "D"}


def _finding(check, severity, detail):
    return {"check": check, "severity": severity, "detail": detail}


def check_missing_values(v):
    missing = v[v["value"].isna()]
    if missing.empty:
        return []
    dates = ", ".join(sorted(missing["obs_date"].dt.strftime("%Y-%m-%d").unique())[:10])
    return [_finding("missing_values", "warning",
                     f"{len(missing)} published values are missing ('.' in FRED). Obs dates: {dates}")]


def check_calendar_gaps(v, frequency="Monthly"):
    cur = latest(v)
    freq = FREQ_MAP.get(frequency)
    if cur.empty or freq is None:
        return []
    expected = pd.date_range(cur.index.min(), cur.index.max(), freq=freq)
    gaps = expected.difference(cur.index)
    if gaps.empty:
        return []
    return [_finding("calendar_gaps", "error",
                     f"{len(gaps)} expected {frequency.lower()} dates missing from latest vintage: "
                     + ", ".join(gaps.strftime("%Y-%m-%d")[:10]))]


def check_realtime_integrity(v):
    """Windows for one observation must not overlap, and exactly one must be open-ended."""
    findings = []
    bad_order = v[v["realtime_end"].notna() & (v["realtime_end"] < v["realtime_start"])]
    if not bad_order.empty:
        findings.append(_finding("realtime_integrity", "error",
                                 f"{len(bad_order)} rows end before they start"))
    overlaps, open_counts = 0, []
    for obs, g in v.groupby("obs_date"):
        g = g.sort_values("realtime_start")
        ends = g["realtime_end"].iloc[:-1]
        next_starts = g["realtime_start"].iloc[1:].values
        overlaps += int(((ends.values >= next_starts) | ends.isna().values).sum())
        n_open = int(g["realtime_end"].isna().sum())
        if n_open != 1:
            open_counts.append((obs.strftime("%Y-%m-%d"), n_open))
    if overlaps:
        findings.append(_finding("realtime_integrity", "error",
                                 f"{overlaps} overlapping real-time windows"))
    if open_counts:
        findings.append(_finding("realtime_integrity", "error",
                                 f"{len(open_counts)} observations without exactly one current value, "
                                 f"e.g. {open_counts[:5]}"))
    return findings


def _robust_z(s):
    med = s.median()
    mad = (s - med).abs().median()
    return (s - med) / (1.4826 * mad) if mad else s * 0


def check_outliers(v, threshold=5.0):
    """Flag unusual period-over-period changes in the latest vintage (median/MAD, robust to outliers)."""
    change = latest(v).diff().dropna()
    z = _robust_z(change)
    flagged = change[z.abs() > threshold]
    if flagged.empty:
        return []
    items = ", ".join(f"{d:%Y-%m} ({x:+,.0f})" for d, x in flagged.head(10).items())
    return [_finding("outliers", "info",
                     f"{len(flagged)} changes beyond {threshold} robust SDs: {items}")]


def check_large_revisions(v, threshold=5.0):
    rev = revision_table(v)
    if rev.empty:
        return []
    r = rev["revision"].dropna()
    flagged = r[_robust_z(r).abs() > threshold]
    if flagged.empty:
        return []
    items = ", ".join(f"{d:%Y-%m} ({x:+,.0f})" for d, x in flagged.head(10).items())
    return [_finding("large_revisions", "warning",
                     f"{len(flagged)} revisions beyond {threshold} robust SDs: {items}")]


def check_staleness(v, max_age_days=45, today=None):
    last = v["realtime_start"].max()
    today = pd.Timestamp(today or datetime.now().date())
    age = (today - last).days
    if age <= max_age_days:
        return []
    return [_finding("staleness", "warning",
                     f"Most recent vintage is {age} days old ({last:%Y-%m-%d}). Refresh the data.")]


def run_all(v, frequency="Monthly", today=None):
    findings = []
    findings += check_missing_values(v)
    findings += check_calendar_gaps(v, frequency)
    findings += check_realtime_integrity(v)
    findings += check_outliers(v)
    findings += check_large_revisions(v)
    findings += check_staleness(v, today=today)
    return findings
