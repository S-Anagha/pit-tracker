import pandas as pd

from pit_tracker.pointintime import as_of, first_release, latest, revision_table


def test_as_of_before_any_release_is_empty(vintages):
    assert as_of(vintages, "2024-01-15").empty


def test_as_of_sees_only_what_was_published(vintages):
    snap = as_of(vintages, "2024-02-20")
    assert list(snap.index) == [pd.Timestamp("2024-01-01")]
    assert snap.iloc[0] == 100


def test_as_of_window_is_inclusive(vintages):
    assert as_of(vintages, "2024-03-05")[pd.Timestamp("2024-01-01")] == 100
    assert as_of(vintages, "2024-03-06")[pd.Timestamp("2024-01-01")] == 101


def test_latest(vintages):
    assert latest(vintages).tolist() == [101, 108, 115]


def test_first_release(vintages):
    fr = first_release(vintages)
    assert fr["first_value"].tolist() == [100, 110, 115]


def test_revision_table(vintages):
    rev = revision_table(vintages)
    feb = rev.loc[pd.Timestamp("2024-02-01")]
    # On Mar 6: Feb 110, Jan 101 -> first change +9. Today: 108 - 101 = +7.
    assert feb["first_change"] == 9
    assert feb["latest_change"] == 7
    assert feb["revision"] == -2
    mar = rev.loc[pd.Timestamp("2024-03-01")]
    assert mar["first_change"] == 7 and mar["revision"] == 0
