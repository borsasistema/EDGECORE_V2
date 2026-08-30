"""
TEST 001 — Fetch 1m OHLCV paths for each coin × day.
Writes immutable raw CSVs with SHA-256 sidecar.
"""

from __future__ import annotations
import os, time, csv
import urllib.request, urllib.parse, json
import pandas as pd
from datetime import datetime, timezone

from core.validator import validate_ohlcv, ValidationError
from core.raw_data  import write_raw
from research.test_001_universe_edge.config import PATH_MINUTES, UTC

BINANCE_BASE = "https://api.binance.com/api/v3"
SLEEP_S      = 0.12
TIMEOUT_S    = 20


class PathFetchError(Exception):
    pass


def _fetch_1m_raw(symbol: str, start_ms: int, n: int) -> list:
    """Fetch exactly n 1m closed candles starting at start_ms."""
    all_candles = []
    cur = start_ms

    while len(all_candles) < n:
        need = min(1000, n - len(all_candles))
        params = {
            "symbol": symbol, "interval": "1m",
            "startTime": cur, "limit": need + 1,
        }
        url = f"{BINANCE_BASE}/klines?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_S) as r:
                chunk = json.loads(r.read())
        except Exception as e:
            raise PathFetchError(f"1m fetch error [{symbol}]: {e}") from e

        if not isinstance(chunk, list) or len(chunk) == 0:
            break

        # Drop the last bar (potentially open)
        chunk = chunk[:-1]
        if not chunk:
            break

        all_candles.extend(chunk)
        cur = int(chunk[-1][0]) + 60_000
        time.sleep(SLEEP_S)

        if len(chunk) < need - 1:
            break  # no more data

    return all_candles[:n]


def _candles_to_df(raw: list) -> pd.DataFrame:
    cols = ["open_time","open","high","low","close","volume",
            "close_time","quote_vol","n","tb","tq","ign"]
    df = pd.DataFrame(raw, columns=cols)
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df["open_time"]  = pd.to_datetime(df["open_time"],  unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    return df[["open_time","open","high","low","close","volume","close_time"]]


def fetch_entry_and_path(
    symbol:    str,
    eval_dt:   datetime,
    raw_dir:   str,
) -> dict:
    """
    Fetches:
      1. Entry price = first 1m candle open with open_time >= eval_dt
      2. 1440 1m closed candles starting from that entry candle

    Returns:
      {
        "status": "OK" | "NO_ENTRY" | "CENSORED" | "INSUFFICIENT",
        "entry_price": float | None,
        "entry_time": str | None,
        "path_file": str | None,
        "path_sha256": str | None,
        "n_candles": int,
      }
    """
    eval_ms   = int(eval_dt.timestamp() * 1000)
    date_str  = eval_dt.strftime("%Y%m%d")
    safe_sym  = symbol.replace("/", "_")
    path_file = os.path.join(raw_dir, f"path_{safe_sym}_{date_str}.csv")

    # ── Entry candle ──────────────────────────────────────────────────────────
    try:
        params = {
            "symbol": symbol, "interval": "1m",
            "startTime": eval_ms, "limit": 2,
        }
        url = f"{BINANCE_BASE}/klines?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as r:
            entry_raw = json.loads(r.read())
        time.sleep(SLEEP_S)
    except Exception as e:
        return {"status": "NO_ENTRY", "entry_price": None, "entry_time": None,
                "path_file": None, "path_sha256": None, "n_candles": 0,
                "detail": str(e)}

    if not isinstance(entry_raw, list) or len(entry_raw) < 2:
        return {"status": "NO_ENTRY", "entry_price": None, "entry_time": None,
                "path_file": None, "path_sha256": None, "n_candles": 0}

    # iloc[0] = potentially open bar; use iloc[0] only if its open_time >= eval_ms
    entry_open_time_ms = int(entry_raw[0][0])
    entry_price        = float(entry_raw[0][1])  # open of that 1m candle
    entry_time_dt      = datetime.fromtimestamp(entry_open_time_ms / 1000, tz=UTC)

    # ── Path (1440 candles starting at entry) ─────────────────────────────────
    start_ms = entry_open_time_ms
    try:
        raw_candles = _fetch_1m_raw(symbol, start_ms, PATH_MINUTES)
    except PathFetchError as e:
        return {"status": "CENSORED", "entry_price": entry_price,
                "entry_time": entry_time_dt.isoformat(),
                "path_file": None, "path_sha256": None, "n_candles": 0,
                "detail": str(e)}

    if len(raw_candles) < PATH_MINUTES:
        return {"status": "CENSORED", "entry_price": entry_price,
                "entry_time": entry_time_dt.isoformat(),
                "path_file": None, "path_sha256": None,
                "n_candles": len(raw_candles),
                "detail": f"only {len(raw_candles)}/{PATH_MINUTES} candles"}

    df = _candles_to_df(raw_candles)

    try:
        validate_ohlcv(df, "1m", context=f"{symbol}_{date_str}", min_rows=PATH_MINUTES)
    except ValidationError as e:
        return {"status": "CENSORED", "entry_price": entry_price,
                "entry_time": entry_time_dt.isoformat(),
                "path_file": None, "path_sha256": None,
                "n_candles": len(df), "detail": str(e)}

    # ── Write immutable raw ───────────────────────────────────────────────────
    csv_text = df.to_csv(index=False)
    try:
        sha = write_raw(path_file, csv_text)
    except Exception:
        sha = write_raw(path_file, csv_text, overwrite=True,
                        justification="re-run overwrites same day/symbol path")

    return {
        "status":      "OK",
        "entry_price": entry_price,
        "entry_time":  entry_time_dt.isoformat(),
        "path_file":   path_file,
        "path_sha256": sha,
        "n_candles":   len(df),
    }
