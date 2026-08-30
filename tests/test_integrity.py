"""
EDGECORE_V2 — Integrity Test Suite
Run: python tests/test_integrity.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
import pandas as pd
import numpy as np
from datetime import timezone

from core.constants import PROJECT_ID, UTC, FEE_RT, FEE_RT_PCT, VALID_INTERVALS, \
    DATA_RAW_DIR, DATA_PROCESSED_DIR, DATA_RESULTS_DIR
from core.validator  import validate_ohlcv, validate_signal_list, fee_assertion, ValidationError
from core.run_meta   import RunMeta
from core.raw_data   import write_raw, read_raw, assert_immutable, ImmutableViolation

_results = []
GREEN = "\033[92m"; RED = "\033[91m"; RESET = "\033[0m"

def test(name, fn):
    try:
        fn()
        print(f"  {GREEN}PASS{RESET}  {name}")
        _results.append((name, True, ""))
    except Exception as e:
        print(f"  {RED}FAIL{RESET}  {name}: {e}")
        _results.append((name, False, str(e)))


def _make_ohlcv(n=50):
    ts    = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    close = 100.0 + np.cumsum(np.random.default_rng(0).standard_normal(n) * 0.5)
    open_ = close + np.random.default_rng(1).standard_normal(n) * 0.1
    high  = np.maximum(open_, close) + np.abs(np.random.default_rng(2).standard_normal(n) * 0.2)
    low   = np.minimum(open_, close) - np.abs(np.random.default_rng(3).standard_normal(n) * 0.2)
    vol   = np.abs(np.random.default_rng(4).standard_normal(n)) * 1000 + 100
    return pd.DataFrame({
        "open_time": ts,
        "open": open_, "high": high, "low": low,
        "close": close, "volume": vol,
    })


_GOOD_SIG = {
    "signal_id": "1", "coin": "BTCUSDT",
    "signal_time_utc": "2026-06-26 09:00:00",
    "entry_price": "43000.0",
}


# ── Constants ─────────────────────────────────────────────────────────────────
def t_project_id():
    assert PROJECT_ID == "EDGECORE_V2", f"Got {PROJECT_ID!r}"

def t_utc():
    assert UTC == timezone.utc

def t_fee_decimal():
    assert FEE_RT == 0.001, f"FEE_RT={FEE_RT!r}"

def t_fee_pct():
    assert FEE_RT_PCT == 0.10

def t_fee_consistent():
    assert abs(FEE_RT * 100 - FEE_RT_PCT) < 1e-9

def t_fee_guard():
    assert 1.8 < (2.0 - FEE_RT * 100) < 2.0
    assert 1.0 < (1.0 + FEE_RT * 100) < 1.2

def t_fee_fn():
    assert fee_assertion() is True

def t_intervals():
    assert "15m" in VALID_INTERVALS and "1h" in VALID_INTERVALS

def t_data_paths():
    for p in (DATA_RAW_DIR, DATA_PROCESSED_DIR, DATA_RESULTS_DIR):
        assert isinstance(p, str) and len(p) > 0


# ── OHLCV validator ───────────────────────────────────────────────────────────
def t_valid_ohlcv():
    df = _make_ohlcv()
    assert validate_ohlcv(df, "15m") is df

def t_missing_col():
    df = _make_ohlcv().drop(columns=["volume"])
    try:
        validate_ohlcv(df, "15m")
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "volume" in str(e).lower()

def t_null_price():
    df = _make_ohlcv()
    df.loc[3, "close"] = float("nan")
    try:
        validate_ohlcv(df, "15m")
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "null" in str(e).lower()

def t_bad_high():
    df = _make_ohlcv()
    df.loc[5, "high"] = df.loc[5, "close"] - 5.0
    try:
        validate_ohlcv(df, "15m")
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "high" in str(e).lower()

def t_bad_low():
    df = _make_ohlcv()
    df.loc[2, "low"] = df.loc[2, "close"] + 5.0
    try:
        validate_ohlcv(df, "15m")
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "low" in str(e).lower()

def t_zero_price():
    df = _make_ohlcv()
    for col in ["open", "high", "low", "close"]:
        df.loc[1, col] = 0.0
    try:
        validate_ohlcv(df, "15m")
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "non-positive" in str(e).lower()

def t_neg_volume():
    df = _make_ohlcv()
    df.loc[0, "volume"] = -1.0
    try:
        validate_ohlcv(df, "15m")
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "volume" in str(e).lower()

def t_min_rows():
    df = _make_ohlcv(5)
    try:
        validate_ohlcv(df, "15m", min_rows=30)
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "too few rows" in str(e).lower()

def t_tz_naive():
    df = _make_ohlcv()
    df["open_time"] = df["open_time"].dt.tz_localize(None)
    try:
        validate_ohlcv(df, "15m")
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "utc" in str(e).lower()

def t_non_monotonic():
    df = _make_ohlcv()
    idx = df.index.tolist()
    idx[3], idx[4] = idx[4], idx[3]
    df = df.loc[idx].reset_index(drop=True)
    try:
        validate_ohlcv(df, "15m")
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "ascending" in str(e).lower()


# ── Signal validator ──────────────────────────────────────────────────────────
def t_valid_sig():
    assert validate_signal_list([_GOOD_SIG])[0] is _GOOD_SIG

def t_missing_key():
    bad = {**_GOOD_SIG}
    del bad["entry_price"]
    try:
        validate_signal_list([bad])
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "entry_price" in str(e)

def t_zero_price_sig():
    try:
        validate_signal_list([{**_GOOD_SIG, "entry_price": "0"}])
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "≤ 0" in str(e)

def t_bad_ts_sig():
    try:
        validate_signal_list([{**_GOOD_SIG, "signal_time_utc": "bad"}])
        raise AssertionError("Expected ValidationError")
    except ValidationError as e:
        assert "unparseable" in str(e).lower()


# ── RunMeta ───────────────────────────────────────────────────────────────────
def t_run_meta():
    with tempfile.TemporaryDirectory() as tmp:
        meta = RunMeta(run_id="T00", description="test")
        meta.params = {"x": 1}
        loaded = RunMeta.load(meta.save(tmp))
        assert loaded.run_id == "T00"
        assert loaded.project_id == "EDGECORE_V2"

def t_input_tracking():
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, "d.csv")
        with open(fp, "w") as f:
            f.write("a,b\n1,2\n")
        meta = RunMeta(run_id="T01", description="t")
        meta.add_input_file("f", fp)
        assert meta.verify_inputs()
        with open(fp, "a") as f:
            f.write("3,4\n")
        try:
            meta.verify_inputs()
            raise AssertionError("Expected RuntimeError")
        except RuntimeError as e:
            assert "modified" in str(e).lower()


# ── Raw data ──────────────────────────────────────────────────────────────────
def t_write_raw():
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, "t.csv")
        sha = write_raw(fp, "a,b\n")
        assert os.path.exists(fp)
        assert os.path.exists(fp + ".sha256")
        assert len(sha) == 64

def t_overwrite_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, "t.csv")
        write_raw(fp, "orig")
        try:
            write_raw(fp, "new")
            raise AssertionError("Expected ImmutableViolation")
        except ImmutableViolation:
            pass

def t_overwrite_needs_just():
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, "t.csv")
        write_raw(fp, "orig")
        try:
            write_raw(fp, "new", overwrite=True, justification="")
            raise AssertionError("Expected ValueError")
        except ValueError:
            pass

def t_overwrite_works():
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, "t.csv")
        write_raw(fp, "orig")
        write_raw(fp, "fixed", overwrite=True, justification="correction")
        assert read_raw(fp) == "fixed"

def t_read_verify():
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, "t.csv")
        write_raw(fp, "data")
        assert read_raw(fp) == "data"

def t_tamper():
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, "t.csv")
        write_raw(fp, "data")
        with open(fp, "w") as f:
            f.write("tampered")
        try:
            read_raw(fp)
            raise AssertionError("Expected ImmutableViolation")
        except ImmutableViolation as e:
            assert "mismatch" in str(e).lower()

def t_assert_immutable():
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, "t.csv")
        write_raw(fp, "ok")
        assert assert_immutable(fp)


# ── Test list ─────────────────────────────────────────────────────────────────
TESTS = [
    ("PROJECT_ID == 'EDGECORE_V2'",          t_project_id),
    ("UTC constant == timezone.utc",          t_utc),
    ("FEE_RT == 0.001 decimal",               t_fee_decimal),
    ("FEE_RT_PCT == 0.10 percent",            t_fee_pct),
    ("FEE_RT and FEE_RT_PCT consistent",      t_fee_consistent),
    ("Fee confusion guard",                   t_fee_guard),
    ("fee_assertion() returns True",          t_fee_fn),
    ("VALID_INTERVALS contains 15m, 1h",      t_intervals),
    ("Data path constants are strings",       t_data_paths),
    ("Valid OHLCV → returns same df",         t_valid_ohlcv),
    ("Missing column → error",               t_missing_col),
    ("Null price → error",                   t_null_price),
    ("high < close → error",                 t_bad_high),
    ("low > close → error",                  t_bad_low),
    ("Zero price → error",                   t_zero_price),
    ("Negative volume → error",              t_neg_volume),
    ("Too few rows → error",                 t_min_rows),
    ("Tz-naïve timestamps → error",          t_tz_naive),
    ("Non-monotonic timestamps → error",     t_non_monotonic),
    ("Valid signal list passes",             t_valid_sig),
    ("Missing signal key → error",           t_missing_key),
    ("Zero price signal → error",            t_zero_price_sig),
    ("Bad timestamp signal → error",         t_bad_ts_sig),
    ("RunMeta save / load round-trip",       t_run_meta),
    ("RunMeta input-file tracking",          t_input_tracking),
    ("write_raw creates file + sidecar",     t_write_raw),
    ("Overwrite blocked by default",         t_overwrite_blocked),
    ("Overwrite needs justification",        t_overwrite_needs_just),
    ("Overwrite with justification works",   t_overwrite_works),
    ("read_raw verifies checksum",           t_read_verify),
    ("Tampered file detected",               t_tamper),
    ("assert_immutable passes on clean file",t_assert_immutable),
]


if __name__ == "__main__":
    print(f"\nEDGECORE_V2  Integrity Test Suite\n{'='*50}")
    for name, fn in TESTS:
        test(name, fn)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n{'='*50}")
    print(f"  {passed}/{len(_results)} passed  |  {failed} failed")
    if failed:
        print("\nFailed tests:")
        for name, ok, err in _results:
            if not ok:
                print(f"  ✗ {name}\n    {err}")
        sys.exit(1)
    else:
        print("  All integrity checks PASS ✓")
        sys.exit(0)
