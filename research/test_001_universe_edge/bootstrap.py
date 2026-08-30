"""
TEST 001 — Day-level bootstrap.
Resampling unit = DAY. Groups weighted equally per day.
"""

from __future__ import annotations
import numpy as np
from typing import Callable

from research.test_001_universe_edge.config import BOOTSTRAP_N, BOOTSTRAP_SEED


def _day_lift(
    obs_by_day: dict[str, dict],
    metric: str,
) -> np.ndarray:
    """
    For each day compute lift = mean_selected(metric) - mean_control_a(metric).
    Returns array of per-day lifts.
    """
    days = sorted(obs_by_day.keys())
    lifts = []
    for d in days:
        sel_vals = [r[metric] for r in obs_by_day[d]["selected"]
                    if r.get("status") == "OK" and metric in r]
        ctl_vals = [r[metric] for r in obs_by_day[d]["control_a"]
                    if r.get("status") == "OK" and metric in r]
        if not sel_vals or not ctl_vals:
            continue
        lifts.append(np.mean(sel_vals) - np.mean(ctl_vals))
    return np.array(lifts)


def bootstrap_metric(
    obs_by_day: dict[str, dict],
    metric: str,
) -> dict:
    """
    Bootstrap CI and prob_lift_le_0 for one metric.

    obs_by_day: {
        "2025-09-01": {
            "selected":  [{"status":"OK", "touch_24h": 1, ...}, ...],
            "control_a": [...],
        }, ...
    }

    Returns:
        lift_mean, ci_lo, ci_hi, bootstrap_prob_lift_le_0
    """
    rng  = np.random.default_rng(BOOTSTRAP_SEED)
    days = sorted(obs_by_day.keys())
    n    = len(days)

    # Observed lift (equal day weights)
    day_lifts_obs = _day_lift(obs_by_day, metric)
    if len(day_lifts_obs) == 0:
        return {
            "lift_mean": None, "ci_lo": None, "ci_hi": None,
            "bootstrap_prob_lift_le_0": None, "n_days": 0,
        }

    lift_mean = float(np.mean(day_lifts_obs))

    # Bootstrap
    boot_lifts = []
    for _ in range(BOOTSTRAP_N):
        sampled_days_idx = rng.integers(0, n, size=n)
        sampled_keys     = [days[i] for i in sampled_days_idx]
        boot_day_obs = {k: obs_by_day[k] for k in sampled_keys}
        bl = _day_lift(boot_day_obs, metric)
        if len(bl) > 0:
            boot_lifts.append(np.mean(bl))

    boot_arr = np.array(boot_lifts)
    ci_lo    = float(np.percentile(boot_arr, 2.5))
    ci_hi    = float(np.percentile(boot_arr, 97.5))
    prob_le0 = float(np.mean(boot_arr <= 0))

    return {
        "lift_mean":                  round(lift_mean, 4),
        "ci_lo":                      round(ci_lo, 4),
        "ci_hi":                      round(ci_hi, 4),
        "bootstrap_prob_lift_le_0":   round(prob_le0, 4),
        "n_days":                     len(day_lifts_obs),
    }


def verdict(ci_lo: float, ci_hi: float) -> str:
    if ci_lo is None or ci_hi is None:
        return "INSUFFICIENT"
    if ci_lo > 0:
        return "HELP"
    if ci_hi < 0:
        return "HURT"
    return "NEUTRAL"
