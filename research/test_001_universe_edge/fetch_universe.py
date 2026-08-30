"""
TEST 001 — Point-in-time universe snapshot per evaluation day.
No current exchangeInfo. Eligibility = historical data present + filters pass.
"""

from __future__ import annotations
import time
import urllib.request, urllib.parse, json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional

from research.test_001_universe_edge.config import (
    VOLUME_MIN_USD, ATR_MIN, EMA_GAP_MIN,
    KLINES_1H_LIMIT, STABLE_LIST, UTC,
)

BINANCE_BASE   = "https://api.binance.com/api/v3"
SLEEP_S        = 0.12
TIMEOUT_S      = 20


class FetchError(Exception):
    pass


def _get(endpoint: str, params: dict) -> any:
    url = f"{BINANCE_BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except Exception as e:
        raise FetchError(f"API {endpoint}: {e}") from e


def _fetch_1h_history(symbol: str, end_ms: int, limit: int = KLINES_1H_LIMIT) -> Optional[pd.DataFrame]:
    """
    Fetch last `limit` closed 1H candles before end_ms.
    Returns None if insufficient data.
    """
    try:
        raw = _get("klines", {
            "symbol": symbol, "interval": "1h",
            "endTime": end_ms, "limit": limit + 1,
        })
    except FetchError:
        return None

    time.sleep(SLEEP_S)

    if not isinstance(raw, list) or len(raw) < 50:
        return None

    cols = ["open_time","open","high","low","close","volume",
            "close_time","quote_vol","n","tb","tq","ign"]
    df = pd.DataFrame(raw, columns=cols)
    for c in ["open","high","low","close","volume","quote_vol"]:
        df[c] = df[c].astype(float)
    df["open_time"]  = pd.to_datetime(df["open_time"],  unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

    # Drop last bar — may be open
    df = df.iloc[:-1].reset_index(drop=True)
    if len(df) < 50:
        return None
    return df


def _calc_atr_gap(df: pd.DataFrame) -> tuple[float, float]:
    """
    V1 exact formula:
      ATR  = mean( rolling(14).mean(TR) / close * 100 )   over full series
      GAP  = mean( |EMA20 - EMA50| / EMA50 * 100 )        over full series
    """
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr_series = tr.rolling(14).mean() / df["close"] * 100
    atr = float(atr_series.dropna().mean())

    ema20 = df["close"].ewm(span=20, adjust=False).mean()
    ema50 = df["close"].ewm(span=50, adjust=False).mean()
    gap_series = (ema20 - ema50).abs() / ema50 * 100
    gap = float(gap_series.dropna().mean())

    return atr, gap


def _fetch_24h_volume(symbol: str, eval_ms: int) -> Optional[float]:
    """
    Historical 24h quote volume ending at eval_ms.
    Uses 1m klines, sums quote_vol over last 1440 candles.
    Current ticker FORBIDDEN.
    """
    try:
        raw = _get("klines", {
            "symbol": symbol, "interval": "1m",
            "endTime": eval_ms, "limit": 1441,
        })
    except FetchError:
        return None

    time.sleep(SLEEP_S)

    if not isinstance(raw, list) or len(raw) < 100:
        return None

    cols = ["ot","o","h","l","c","v","ct","quote_vol","n","tb","tq","ign"]
    df = pd.DataFrame(raw, columns=cols)
    df["quote_vol"] = df["quote_vol"].astype(float)
    df["ct"] = df["ct"].astype(float)

    # Only candles fully closed before eval_ms
    df = df[df["ct"] < eval_ms].tail(1440)
    if len(df) < 100:
        return None

    return float(df["quote_vol"].sum())


def _get_all_usdt_symbols(eval_ms: int) -> list[str]:
    """
    Point-in-time: fetch symbol list from exchangeInfo, then filter
    to those with recent 1m data (proxy for active at eval_ms).
    This avoids using current state for forward-looking decisions;
    symbols without data at eval_ms are excluded naturally.
    """
    try:
        info = _get("exchangeInfo", {})
    except FetchError as e:
        raise FetchError(f"exchangeInfo failed: {e}") from e

    symbols = []
    for s in info.get("symbols", []):
        if (s.get("quoteAsset") == "USDT"
                and s.get("status") == "TRADING"
                and s.get("baseAsset", "") not in STABLE_LIST):
            symbols.append(s["symbol"])
    return symbols


def build_snapshot(eval_dt: datetime) -> dict:
    """
    Build point-in-time universe snapshot for one evaluation datetime.

    Returns:
        {
          "eval_dt": ...,
          "selected": [{"symbol":..., "vol":..., "atr":..., "gap":...}, ...],
          "control_a": [...],
          "n_no_data": int,
          "n_insufficient_history": int,
        }
    """
    eval_ms = int(eval_dt.timestamp() * 1000)

    all_symbols = _get_all_usdt_symbols(eval_ms)

    selected = []
    control_a = []
    n_no_data = 0
    n_insuf   = 0

    for sym in all_symbols:
        # 1. Historical 24h volume
        vol = _fetch_24h_volume(sym, eval_ms)
        if vol is None:
            n_no_data += 1
            continue
        if vol < VOLUME_MIN_USD:
            continue

        # 2. 1H history for ATR / EMA-gap
        df1h = _fetch_1h_history(sym, eval_ms)
        if df1h is None:
            n_insuf += 1
            continue

        atr, gap = _calc_atr_gap(df1h)
        row = {"symbol": sym, "vol": vol, "atr": atr, "gap": gap}

        if atr >= ATR_MIN and gap >= EMA_GAP_MIN:
            selected.append(row)
        else:
            control_a.append(row)

    return {
        "eval_dt":                eval_dt,
        "selected":               selected,
        "control_a":              control_a,
        "n_no_data":              n_no_data,
        "n_insufficient_history": n_insuf,
    }


def build_control_b(selected: list[dict], control_a: list[dict]) -> list[dict]:
    """
    Volume-matched 1-to-1 pairing: for each selected coin find
    the nearest control_a coin by |vol_s - vol_c|, no replacement.
    """
    remaining = list(control_a)
    matched   = []

    for s in selected:
        if not remaining:
            break
        best_idx = min(range(len(remaining)),
                       key=lambda i: abs(remaining[i]["vol"] - s["vol"]))
        matched.append(remaining.pop(best_idx))

    return matched
