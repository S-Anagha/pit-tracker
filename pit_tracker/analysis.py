"""Revision analysis and a short markdown report."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .pointintime import revision_table


def summarize(rev):
    """Headline revision statistics, with and without the 2020 shock."""
    def stats(r):
        r = r.dropna(subset=["revision"])
        if r.empty:
            return {}
        return {
            "months": len(r),
            "mean_revision": r["revision"].mean(),
            "mean_abs_revision": r["revision"].abs().mean(),
            "median_abs_revision": r["revision"].abs().median(),
            "sign_flips": int((r["first_change"] * r["latest_change"] < 0).sum()),
            "largest_up": (r["revision"].idxmax(), r["revision"].max()),
            "largest_down": (r["revision"].idxmin(), r["revision"].min()),
        }

    return {"all": stats(rev), "excl_2020": stats(rev[rev.index.year != 2020])}


def plot_revisions(rev, series_id, out_dir):
    out = Path(out_dir) / f"{series_id}_revisions.png"
    r = rev.dropna(subset=["revision"])
    r = r[r.index.year != 2020]  # 2020 swamps the scale; it is reported separately in the text
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(r.index, r["first_change"], label="As first reported", lw=1)
    axes[0].plot(r.index, r["latest_change"], label="As it stands today", lw=1)
    axes[0].set_title(f"{series_id}: period-over-period change (excluding 2020)")
    axes[0].legend()
    axes[1].bar(r.index, r["revision"], width=20)
    axes[1].axhline(0, color="black", lw=0.5)
    axes[1].set_title("Total revision (today minus first report)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def _fmt(x):
    return f"{x:+,.1f}"


def write_report(series_id, meta, v, findings, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rev = revision_table(v)
    summary = summarize(rev) if not rev.empty else {}
    chart = plot_revisions(rev, series_id, out_dir) if not rev.empty else None

    lines = [f"# {series_id}: point-in-time and revision report", ""]
    if meta:
        lines += [
            "## Metadata", "",
            f"- Title: {meta.get('title')}",
            f"- Units: {meta.get('units')}",
            f"- Frequency: {meta.get('frequency')}",
            f"- Seasonal adjustment: {meta.get('seasonal_adjustment')}",
            f"- Source last updated: {meta.get('source_last_updated')}",
            f"- Fetched: {meta.get('fetched_at')}", "",
        ]
    lines += [
        "## Coverage", "",
        f"- Vintage rows: {len(v):,}",
        f"- Observations: {v['obs_date'].nunique():,} "
        f"({v['obs_date'].min():%Y-%m} to {v['obs_date'].max():%Y-%m})",
        f"- Distinct vintages: {v['realtime_start'].nunique():,}", "",
        "## Quality checks", "",
    ]
    if findings:
        lines += [f"- **{f['severity']}** `{f['check']}`: {f['detail']}" for f in findings]
    else:
        lines.append("- All checks passed.")
    lines.append("")

    for key, label in (("all", "All periods"), ("excl_2020", "Excluding 2020")):
        s = summary.get(key)
        if not s:
            continue
        up_d, up_v = s["largest_up"]
        dn_d, dn_v = s["largest_down"]
        lines += [
            f"## Revisions: {label.lower()}", "",
            f"- Periods compared: {s['months']}",
            f"- Mean revision: {_fmt(s['mean_revision'])} (positive means first reports ran low)",
            f"- Mean absolute revision: {s['mean_abs_revision']:,.1f}",
            f"- Median absolute revision: {s['median_abs_revision']:,.1f}",
            f"- Periods where the direction changed after revision: {s['sign_flips']}",
            f"- Largest upward revision: {up_d:%Y-%m} ({_fmt(up_v)})",
            f"- Largest downward revision: {dn_d:%Y-%m} ({_fmt(dn_v)})", "",
        ]
    if chart:
        lines += ["## Chart", "", f"![revisions]({chart.name})", ""]

    report = out_dir / f"{series_id}_report.md"
    report.write_text("\n".join(lines))
    if not rev.empty:
        rev.to_csv(out_dir / f"{series_id}_revisions.csv")
    return report
