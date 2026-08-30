"""
EDGECORE_V2 — OHLCV & Signal Validator
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from typing import List, Dict, Any


class ValidationError(Exception):
    pass


def validate_ohlcv(
    df: pd.DataFrame,
    interval: str,
    context: str = "",
    min_rows: int = 30,
) -> pd.DataFrame:
    ctx = f"[{context}] " if context else ""

    required = {"open", "high", "low", "close", "volume"}
    missing  = required - set(df.columns)
    if missing:
        raise ValidationError(f"{ctx}Missing columns: {sorted(missing)}")

    null_counts = df[list(required)].isnull().sum()
    bad = null_counts[null_counts > 0]
    if not bad.empty:
        raise ValidationError(f"{ctx}Null values — {bad.to_dict()}")

    max_oc = df[["open", "close"]].max(axis=1)
    min_oc = df[["open", "close"]].min(axis=1)

    if (df["high"] < max_oc).any():
        raise ValidationError(f"{ctx}high < max(open,close) on {(df['high'] < max_oc).sum()} row(s)")
    if (df["low"] > min_oc).any():
        raise ValidationError(f"{ctx}low > min(open,close) on {(df['low'] > min_oc).sum()} row(s)")

    nonpos = (df[["open", "high", "low", "close"]] <= 0)
    if nonpos.any(axis=None):
        raise ValidationError(f"{ctx}Non-positive price on {nonpos.any(axis=1).sum()} row(s)")

    if (df["volume"] < 0).any():
        raise ValidationError(f"{ctx}Negative volume on {(df['volume'] < 0).sum()} row(s)")

    time_col = next(
        (c for c in ("open_time", "open_dt", "timestamp", "ts") if c in df.columns),
        None,
    )
    if time_col is not None:
        parsed = pd.to_datetime(df[time_col], errors="coerce")
        if parsed.isnull().any():
            raise ValidationError(f"{ctx}Unparseable timestamps in '{time_col}'")
        if parsed.dt.tz is None:
            raise ValidationError(f"{ctx}'{time_col}' is tz-naïve — must be UTC-aware")
        if not parsed.is_monotonic_increasing:
            raise ValidationError(f"{ctx}'{time_col}' is not in ascending order")
        dups = parsed.duplicated().sum()
        if dups:
            raise ValidationError(f"{ctx}'{time_col}' has {dups} duplicate(s)")

    if len(df) < min_rows:
        raise ValidationError(f"{ctx}Too few rows: got {len(df)}, need ≥ {min_rows}")

    return df


def validate_signal_list(
    signals: List[Dict[str, Any]],
    context: str = "",
) -> List[Dict[str, Any]]:
    ctx = f"[{context}] " if context else ""
    required_keys = {"signal_id", "coin", "signal_time_utc", "entry_price"}

    for i, s in enumerate(signals):
        missing = required_keys - set(s.keys())
        if missing:
            raise ValidationError(f"{ctx}Signal #{i} missing keys: {sorted(missing)}")
        try:
            price = float(s["entry_price"])
        except (TypeError, ValueError):
            raise ValidationError(f"{ctx}Signal #{i}: non-numeric entry_price={s['entry_price']!r}")
        if price <= 0:
            raise ValidationError(f"{ctx}Signal #{i}: entry_price={price} ≤ 0")
        ts_raw = str(s["signal_time_utc"]).replace(" ", "T")
        if "+" not in ts_raw and "Z" not in ts_raw:
            ts_raw += "+00:00"
        try:
            pd.Timestamp(ts_raw, tz="UTC")
        except Exception:
            raise ValidationError(f"{ctx}Signal #{i}: unparseable signal_time_utc={s['signal_time_utc']!r}")

    return signals


def fee_assertion() -> bool:
    from core.constants import FEE_RT, FEE_RT_PCT
    assert FEE_RT == 0.001
    assert FEE_RT_PCT == 0.10
    assert 1.8 < (2.0 - FEE_RT * 100) < 2.0
    assert 1.0 < (1.0 + FEE_RT * 100) < 1.2
    return True
