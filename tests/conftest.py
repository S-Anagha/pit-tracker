import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pit_tracker.store import prepare  # noqa: E402

OPEN = "9999-12-31"


def make_vintages():
    """A tiny hand-built history.

    Jan is first published at 100 on Feb 7, revised to 101 on Mar 6.
    Feb is first published at 110 on Mar 6, revised to 108 on Apr 3.
    Mar is first published at 115 on Apr 3 and not revised yet.
    """
    rows = [
        ("2024-01-01", "2024-02-07", "2024-03-05", 100),
        ("2024-01-01", "2024-03-06", OPEN, 101),
        ("2024-02-01", "2024-03-06", "2024-04-02", 110),
        ("2024-02-01", "2024-04-03", OPEN, 108),
        ("2024-03-01", "2024-04-03", OPEN, 115),
    ]
    return prepare(pd.DataFrame(rows, columns=["obs_date", "realtime_start", "realtime_end", "value"]))


@pytest.fixture
def vintages():
    return make_vintages()
