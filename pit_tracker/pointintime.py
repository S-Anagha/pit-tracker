"""Point-in-time views of a vintage history.

The key idea: a backtest must only see numbers that were published at the time.
as_of(v, date) returns the series exactly as a person would have seen it that day.
"""
import pandas as pd


def as_of(v, date):
    """The series as published on `date` (real-time windows are inclusive on both ends)."""
    d = pd.Timestamp(date)
    live = (v["realtime_start"] <= d) & (v["realtime_end"].isna() | (v["realtime_end"] >= d))
    return v.loc[live].set_index("obs_date")["value"].sort_index()


def latest(v):
    """The current vintage: rows with an open-ended real-time window."""
    return v.loc[v["realtime_end"].isna()].set_index("obs_date")["value"].sort_index()


def first_release(v):
    """First published value and publication date for each observation."""
    first = v.loc[v.groupby("obs_date")["realtime_start"].idxmin()]
    return first.set_index("obs_date")[["realtime_start", "value"]].rename(
        columns={"realtime_start": "release_date", "value": "first_value"}
    )


def revision_table(v):
    """For each period, compare the change as first reported with the change as it stands today.

    For a level series like payrolls, the market cares about the monthly change.
    The first-reported change uses the snapshot on release day, where the prior
    month has usually already been revised once. That matches the headline number.
    """
    fr = first_release(v)
    cur = latest(v)
    obs_dates = list(fr.index)
    records = []
    for prev, t in zip(obs_dates[:-1], obs_dates[1:]):
        release = fr.at[t, "release_date"]
        snap = as_of(v, release)
        if t not in snap.index or prev not in snap.index:
            continue
        first_change = snap[t] - snap[prev]
        latest_change = cur.get(t) - cur.get(prev) if t in cur.index and prev in cur.index else float("nan")
        records.append({
            "obs_date": t,
            "release_date": release,
            "first_change": first_change,
            "latest_change": latest_change,
            "revision": latest_change - first_change,
        })
    return pd.DataFrame(records).set_index("obs_date") if records else pd.DataFrame()
