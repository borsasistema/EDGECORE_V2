"""
TEST 001 — Main runner.
Usage:
    python -m research.test_001_universe_edge.run --smoke
    python -m research.test_001_universe_edge.run --full
"""

from __future__ import annotations
import argparse, os, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from core.run_meta  import RunMeta
from core.constants import DATA_RAW_DIR, DATA_RESULTS_DIR
from research.test_001_universe_edge.config import (
    FULL_START, FULL_END, SMOKE_DAYS, EVAL_HOUR, EVAL_MINUTE,
    BOOTSTRAP_N, UTC, TEST_ID,
)
from research.test_001_universe_edge.fetch_universe import build_snapshot, build_control_b
from research.test_001_universe_edge.fetch_paths    import fetch_entry_and_path
from research.test_001_universe_edge.evaluate       import compute_metrics, load_path
from research.test_001_universe_edge.bootstrap      import bootstrap_metric
from research.test_001_universe_edge.report         import print_report, write_results_csv


def _eval_days(start: str, end: str, limit: int | None) -> list[datetime]:
    d   = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=UTC)
    end_dt = datetime.strptime(end,   "%Y-%m-%d").replace(tzinfo=UTC)
    days = []
    while d <= end_dt:
        days.append(d.replace(hour=EVAL_HOUR, minute=EVAL_MINUTE))
        d += timedelta(days=1)
        if limit and len(days) >= limit:
            break
    return days


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true",
                        help=f"Run first {SMOKE_DAYS} days only (technical validation)")
    parser.add_argument("--full",  action="store_true",
                        help="Run full period 2025-09-01 → 2026-08-29")
    args = parser.parse_args()

    if not args.smoke and not args.full:
        parser.error("Specify --smoke or --full")

    smoke  = args.smoke
    limit  = SMOKE_DAYS if smoke else None
    run_id = f"{TEST_ID}_{'smoke' if smoke else 'full'}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

    raw_dir     = os.path.join(DATA_RAW_DIR,     "test001")
    results_dir = os.path.join(DATA_RESULTS_DIR, "test001")
    os.makedirs(raw_dir,     exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    meta = RunMeta(run_id=run_id,
                   description=f"TEST 001 universe edge {'SMOKE' if smoke else 'FULL'}")
    meta.params = {
        "smoke": smoke, "full_start": FULL_START, "full_end": FULL_END,
        "smoke_days": SMOKE_DAYS, "bootstrap_n": BOOTSTRAP_N,
    }

    eval_days = _eval_days(FULL_START, FULL_END, limit)
    print(f"\n{run_id}  —  {len(eval_days)} evaluation days")

    all_obs:     list[dict] = []
    obs_by_day:  dict       = {}

    for eval_dt in eval_days:
        date_str = eval_dt.strftime("%Y-%m-%d")
        print(f"\n  [{date_str}] building snapshot...", end=" ", flush=True)

        snap = build_snapshot(eval_dt)
        ctrl_b = build_control_b(snap["selected"], snap["control_a"])

        print(f"SEL={len(snap['selected'])} CTL_A={len(snap['control_a'])} CTL_B={len(ctrl_b)}")

        obs_by_day[date_str] = {"selected": [], "control_a": [], "control_b": []}

        for group_name, coins in [
            ("SELECTED",  snap["selected"]),
            ("CONTROL_A", snap["control_a"]),
            ("CONTROL_B", ctrl_b),
        ]:
            for coin_row in coins:
                sym = coin_row["symbol"]
                path_info = fetch_entry_and_path(sym, eval_dt, raw_dir)

                obs: dict = {
                    "date":        date_str,
                    "symbol":      sym,
                    "group":       group_name,
                    "status":      path_info["status"],
                    "entry_price": path_info.get("entry_price"),
                    "entry_time":  path_info.get("entry_time"),
                    "vol":         coin_row["vol"],
                    "atr":         coin_row.get("atr"),
                    "gap":         coin_row.get("gap"),
                    "path_sha256": path_info.get("path_sha256"),
                    "n_candles":   path_info.get("n_candles", 0),
                }

                if path_info["status"] == "OK":
                    df = load_path(path_info["path_file"])
                    if df is not None and len(df) >= 60:
                        metrics = compute_metrics(path_info["entry_price"], df)
                        obs.update(metrics)
                    else:
                        obs["status"] = "CENSORED"
                        obs["detail"] = "path load failed"

                all_obs.append(obs)
                grp_key = group_name.lower().replace("-", "_")
                obs_by_day[date_str][grp_key].append(obs)

    # ── Metrics list ──────────────────────────────────────────────────────────
    metric_keys = [
        "touch_24h","touch_8h","touch_4h","touch_1h","win_24h",
        "mfe_24h","mae_24h","ret_24h","absmove_24h",
        "mfe_8h","mae_8h","mfe_4h","mae_4h","mfe_1h","mae_1h",
    ]

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    print("\n  Running bootstrap...")
    bootstrap_results = {}
    for mk in metric_keys:
        bootstrap_results[mk] = bootstrap_metric(obs_by_day, mk)

    # ── Report ────────────────────────────────────────────────────────────────
    print_report(all_obs, bootstrap_results, run_id, smoke=smoke)

    csv_path = os.path.join(results_dir, f"{run_id}_obs.csv")
    write_results_csv(all_obs, csv_path)

    bs_path = os.path.join(results_dir, f"{run_id}_bootstrap.json")
    import json
    with open(bs_path, "w") as f:
        json.dump(bootstrap_results, f, indent=2)

    meta.save(results_dir)
    print(f"  Results: {csv_path}")


if __name__ == "__main__":
    main()
