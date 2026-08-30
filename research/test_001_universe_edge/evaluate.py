"""
TEST 001 — Per-observation metric computation.
Lookahead-free. Worst-case LOSS on same-candle TP+SL.
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional
from research.test_001_universe_edge.config import (
    TP_PCT, SL_PCT, HORIZONS_H, PATH_MINUTES,
)


def compute_metrics(
    entry_price: float,
    path_df: pd.DataFrame,
) -> dict:
    """
    path_df: 1440-row DataFrame with columns open,high,low,close
    Returns dict of all metrics for one (coin, day) observation.
    """
    tp_price = entry_price * (1 + TP_PCT / 100)
    sl_price = entry_price * (1 - SL_PCT / 100)

    highs  = path_df["high"].values
    lows   = path_df["low"].values
    closes = path_df["close"].values

    n = len(highs)

    # ── Running MFE / MAE ─────────────────────────────────────────────────────
    running_high = np.maximum.accumulate(highs)
    running_low  = np.minimum.accumulate(lows)

    # ── TP / SL outcome ───────────────────────────────────────────────────────
    tp2_min = sl1_min = None
    for i in range(n):
        tp_hit = highs[i] >= tp_price
        sl_hit = lows[i]  <= sl_price
        if tp_hit and sl_hit:
            # worst-case: LOSS (both in same candle)
            if sl1_min is None:
                sl1_min = i + 1   # 1-indexed minute
            break
        if tp_hit and tp2_min is None:
            tp2_min = i + 1
        if sl_hit and sl1_min is None:
            sl1_min = i + 1
        if tp2_min is not None or sl1_min is not None:
            break

    win_24h = (
        tp2_min is not None
        and (sl1_min is None or tp2_min < sl1_min)
    )

    # ── Per-horizon metrics ───────────────────────────────────────────────────
    result: dict = {
        "win_24h":   int(win_24h),
        "tp2_min":   tp2_min,
        "sl1_min":   sl1_min,
        "touch_24h": int(running_high[-1] >= tp_price),
    }

    for h in HORIZONS_H:
        idx = min(h * 60, n) - 1        # 0-indexed last minute of horizon
        if idx < 0:
            continue
        rh = running_high[idx]
        rl = running_low[idx]
        cl = closes[idx]

        mfe = (rh / entry_price - 1) * 100
        mae = (rl / entry_price - 1) * 100   # negative, polarity preserved
        ret = (cl / entry_price - 1) * 100
        tch = int(rh >= tp_price)

        result[f"mfe_{h}h"]   = round(mfe, 4)
        result[f"mae_{h}h"]   = round(mae, 4)   # negative
        result[f"ret_{h}h"]   = round(ret, 4)
        result[f"absmove_{h}h"] = round(abs(ret), 4)
        result[f"touch_{h}h"] = tch

    return result


def load_path(path_file: str) -> Optional[pd.DataFrame]:
    try:
        df = pd.read_csv(path_file, parse_dates=["open_time"])
        for c in ["open","high","low","close"]:
            df[c] = df[c].astype(float)
        return df
    except Exception:
        return None
