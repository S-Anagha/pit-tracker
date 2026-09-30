import pandas as pd

from pit_tracker.qc import (check_calendar_gaps, check_missing_values, check_realtime_integrity,
                            check_staleness, run_all)


def test_clean_data_passes(vintages):
    assert run_all(vintages, today="2024-04-10") == []


def test_detects_missing_value(vintages):
    v = vintages.copy()
    v.loc[0, "value"] = float("nan")
    assert check_missing_values(v)[0]["check"] == "missing_values"


def test_detects_calendar_gap(vintages):
    v = vintages[vintages["obs_date"] != pd.Timestamp("2024-02-01")]
    assert check_calendar_gaps(v)[0]["severity"] == "error"


def test_detects_overlapping_windows(vintages):
    v = vintages.copy()
    v.loc[0, "realtime_end"] = pd.Timestamp("2024-03-10")  # overlaps the Mar 6 revision
    assert any("overlapping" in f["detail"] for f in check_realtime_integrity(v))


def test_detects_two_current_values(vintages):
    v = vintages.copy()
    v.loc[0, "realtime_end"] = pd.NaT
    assert check_realtime_integrity(v)


def test_staleness(vintages):
    assert check_staleness(vintages, today="2024-04-10") == []
    assert check_staleness(vintages, today="2024-09-01")[0]["check"] == "staleness"
