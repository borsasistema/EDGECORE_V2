"""
EDGECORE_V2 — Market Data
Binance Spot public API. Only closed candles. Fail-fast on any error.
"""

from __future__ import annotations
import hashlib, time
import urllib.request, urllib.parse, json
import pandas as pd
from datetime import datetime, timezone
from core.validator import validate_ohlcv, ValidationError

BINANCE_BASE = "https://api.binance.com/api/v3"
SLEEP_S      = 0.12
TIMEOUT_S    = 20


class MarketDataError(Exception):
    pass


def _fetch_klines(symbol: str, interval: str, limit: int, end_ms: int | None = None) -> list:
    params: dict = {"symbol": symbol, "interval": interval, "limit": limit}
    if end_ms is not None:
        params["endTime"] = end_ms
    url = f"{BINANCE_BASE}/klines?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as r:
            data = json.loads(r.read())
    except Exception as e:
        raise MarketDataError(f"API error [{symbol} {interval}]: {e}") from e
    if not isinstance(data, list) or len(data) == 0:
        raise MarketDataError(f"Empty response [{symbol} {interval}]")
    return data


def _to_df(raw: list) -> pd.DataFrame:
    cols = ["open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "tb", "tq", "ignore"]
    df = pd.DataFrame(raw, columns=cols)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df["open_time"]  = pd.to_datetime(df["open_time"],  unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    return df


def fetch_closed_candles(
    symbol:   str,
    interval: str,
    limit:    int = 100,
    end_ms:   int | None = None,
    context:  str = "",
) -> pd.DataFrame:
    """
    Fetch closed candles only.

    Live call (end_ms=None):  drops the last bar with df.iloc[:-1] because
                              that bar is still open at request time.
    Historical call (end_ms): Binance returns bars whose open_time <= end_ms,
                              so the last bar may still be open; drop it too.

    Raises MarketDataError or ValidationError — never silently continues.
    """
    raw  = _fetch_klines(symbol, interval, limit + 1, end_ms)
    df   = _to_df(raw)

    # Drop the last bar — it may be open regardless of end_ms
    df = df.iloc[:-1].reset_index(drop=True)

    if df.empty:
        raise MarketDataError(f"No closed candles after drop [{symbol} {interval}]")

    ctx = context or f"{symbol}_{interval}"
    validate_ohlcv(df, interval, context=ctx)

    time.sleep(SLEEP_S)
    return df


def fetch_open_candle_included(
    symbol:   str,
    interval: str,
    limit:    int = 10,
) -> pd.DataFrame:
    """
    Intentionally includes the open (last) candle.
    Used ONLY in tests that verify open-candle rejection.
    Do NOT use in research or production logic.
    """
    raw = _fetch_klines(symbol, interval, limit)
    df  = _to_df(raw)
    time.sleep(SLEEP_S)
    return df


def candle_sha256(df: pd.DataFrame) -> str:
    """Deterministic SHA-256 of a candle DataFrame's OHLCV values."""
    key = df[["open_time", "open", "high", "low", "close", "volume"]].to_csv(index=False)
    return hashlib.sha256(key.encode()).hexdigest()


def last_closed_time(df: pd.DataFrame) -> str:
    """ISO-8601 UTC string of the last candle's open_time."""
    ts = df["open_time"].iloc[-1]
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)
