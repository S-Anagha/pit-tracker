"""Command line entry point.

  python -m pit_tracker fetch  --series PAYEMS --start 2000-01-01
  python -m pit_tracker qc     --series PAYEMS
  python -m pit_tracker report --series PAYEMS
  python -m pit_tracker asof   --series PAYEMS --date 2020-06-01 --last 6
"""
import argparse
from pathlib import Path

from . import store
from .analysis import write_report
from .pointintime import as_of, latest
from .qc import run_all

DEFAULT_DB = Path("data") / "vintages.db"


def cmd_fetch(args):
    from .fredapi import FredClient

    client = FredClient()
    print(f"Fetching metadata for {args.series}...")
    info = client.series_info(args.series)
    print(f"Fetching all vintages since {args.start} (this can take a minute)...")
    rows = client.all_vintages(args.series, observation_start=args.start)
    conn = store.connect(args.db)
    store.save_series(conn, info)
    store.save_vintages(conn, args.series, rows)
    print(f"Stored {len(rows):,} vintage rows for {args.series} in {args.db}")


def _load(args):
    conn = store.connect(args.db)
    v = store.load_vintages(conn, args.series)
    if v.empty:
        raise SystemExit(f"No data for {args.series}. Run: python -m pit_tracker fetch --series {args.series}")
    return v, store.load_series(conn, args.series)


def cmd_qc(args):
    v, meta = _load(args)
    findings = run_all(v, frequency=(meta or {}).get("frequency", "Monthly"))
    if not findings:
        print("All checks passed.")
    for f in findings:
        print(f"[{f['severity']:>7}] {f['check']}: {f['detail']}")


def cmd_report(args):
    v, meta = _load(args)
    findings = run_all(v, frequency=(meta or {}).get("frequency", "Monthly"))
    path = write_report(args.series, meta, v, findings, args.out)
    print(f"Report written to {path}")


def cmd_asof(args):
    v, _ = _load(args)
    snap = as_of(v, args.date).tail(args.last)
    cur = latest(v).reindex(snap.index)
    print(f"{args.series} as published on {args.date} vs today:")
    print(f"{'obs':<10}{'then':>14}{'today':>14}{'diff':>12}")
    for d in snap.index:
        print(f"{d:%Y-%m}   {snap[d]:>14,.1f}{cur[d]:>14,.1f}{cur[d] - snap[d]:>+12,.1f}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="pit_tracker", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite path (default: data/vintages.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="Download metadata and all vintages from ALFRED")
    f.add_argument("--series", default="PAYEMS")
    f.add_argument("--start", default="2000-01-01", help="First observation date to pull")
    f.set_defaults(func=cmd_fetch)

    for name, func, help_ in (("qc", cmd_qc, "Run data quality checks"),
                              ("report", cmd_report, "Write the markdown report and chart")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--series", default="PAYEMS")
        s.add_argument("--out", default="output")
        s.set_defaults(func=func)

    a = sub.add_parser("asof", help="Show the series as it was published on a date")
    a.add_argument("--series", default="PAYEMS")
    a.add_argument("--date", required=True)
    a.add_argument("--last", type=int, default=6, help="How many recent observations to show")
    a.set_defaults(func=cmd_asof)

    args = p.parse_args(argv)
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    args.func(args)
