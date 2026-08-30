"""
TEST 001 — Terminal and CSV report.
"""

from __future__ import annotations
import os, csv, json
from datetime import datetime, timezone
from research.test_001_universe_edge.bootstrap import verdict
from research.test_001_universe_edge.config import CENSOR_WARN_PCT


METRICS_ORDER = [
    ("touch_24h",    "+2_touch_24h   ← PRIMARY"),
    ("touch_8h",     "+2_touch_8h"),
    ("touch_4h",     "+2_touch_4h"),
    ("touch_1h",     "+2_touch_1h"),
    ("win_24h",      "+2_before_1_24h"),
    ("mfe_24h",      "MFE_24h"),
    ("mae_24h",      "MAE_24h (neg=risk)"),
    ("ret_24h",      "abs_return_24h"),
    ("absmove_24h",  "abs_move_24h"),
    ("mfe_8h",       "MFE_8h"),
    ("mae_8h",       "MAE_8h"),
    ("mfe_4h",       "MFE_4h"),
    ("mae_4h",       "MAE_4h"),
    ("mfe_1h",       "MFE_1h"),
    ("mae_1h",       "MAE_1h"),
]


def _group_stats(obs: list[dict], metric: str) -> dict:
    vals = [r[metric] for r in obs if r.get("status") == "OK" and metric in r]
    if not vals:
        return {"n": 0, "mean": None, "median": None}
    import numpy as np
    return {
        "n":      len(vals),
        "mean":   round(float(np.mean(vals)),   4),
        "median": round(float(np.median(vals)), 4),
    }


def print_report(
    all_obs:      list[dict],
    bootstrap_results: dict[str, dict],
    run_id:       str,
    smoke:        bool = False,
) -> None:
    sel = [r for r in all_obs if r["group"] == "SELECTED" and r["status"] == "OK"]
    ctl = [r for r in all_obs if r["group"] == "CONTROL_A" and r["status"] == "OK"]
    ctb = [r for r in all_obs if r["group"] == "CONTROL_B" and r["status"] == "OK"]
    cen = [r for r in all_obs if r["status"] == "CENSORED"]
    n_total = len(all_obs)
    n_cen   = len(cen)
    cen_pct = round(n_cen / n_total * 100, 1) if n_total else 0

    print(f"\n{'='*72}")
    print(f"  EDGECORE_V2  {run_id}  {'[SMOKE RUN]' if smoke else ''}")
    print(f"  UTC: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*72}")
    print(f"\n  SAMPLE")
    print(f"  {'SELECTED':12}  n={len(sel)}")
    print(f"  {'CONTROL_A':12}  n={len(ctl)}")
    print(f"  {'CONTROL_B':12}  n={len(ctb)}")
    print(f"\n  SURVIVORSHIP")
    print(f"  Total observations : {n_total}")
    print(f"  Censored           : {n_cen}  ({cen_pct}%)")
    if cen_pct > CENSOR_WARN_PCT:
        print(f"  ⚠  WARNING: censor rate {cen_pct}% > {CENSOR_WARN_PCT}% threshold")

    print(f"\n  {'Metric':<25} {'SEL mean':>10} {'CTL_A mean':>11} "
          f"{'lift':>8} {'CI_lo':>8} {'CI_hi':>8} {'p_le0':>7} {'Verdict':>9}")
    print(f"  {'-'*90}")

    for key, label in METRICS_ORDER:
        bs  = bootstrap_results.get(key, {})
        ss  = _group_stats(sel, key)
        cs  = _group_stats(ctl, key)
        lift   = bs.get("lift_mean")
        ci_lo  = bs.get("ci_lo")
        ci_hi  = bs.get("ci_hi")
        p_le0  = bs.get("bootstrap_prob_lift_le_0")
        verd   = verdict(ci_lo, ci_hi)

        def fmt(v): return f"{v:>10.3f}" if v is not None else f"{'—':>10}"

        primary_mark = " ◄" if "PRIMARY" in label else ""
        print(f"  {label:<25} {fmt(ss.get('mean'))} {fmt(cs.get('mean'))} "
              f"{fmt(lift)} {fmt(ci_lo)} {fmt(ci_hi)} "
              f"{f'{p_le0:.3f}':>7} {verd:>9}{primary_mark}")

    print(f"\n{'='*72}\n")


def write_results_csv(all_obs: list[dict], path: str) -> None:
    if not all_obs:
        return
    keys = sorted({k for r in all_obs for k in r.keys()})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(all_obs)
