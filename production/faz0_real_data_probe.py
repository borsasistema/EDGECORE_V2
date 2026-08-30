"""
EDGECORE_V2 — FAZ 0 Real Data Probe (Production)
Lightweight live check: fetches closed candles, validates, reports.
Uses the same core/market_data as research. Fail-fast.
Run: python production/faz0_real_data_probe.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from core.market_data import (
    fetch_closed_candles, candle_sha256, last_closed_time, MarketDataError,
)
from core.validator import ValidationError

SYMBOL    = "BTCUSDT"
INTERVALS = ["1m", "15m", "1h"]

print(f"\nEDGECORE_V2  FAZ 0 — Production Data Probe")
print(f"UTC now : {datetime.now(timezone.utc).isoformat()}")
print("=" * 60)

passed = 0
failed = 0

for iv in INTERVALS:
    try:
        df  = fetch_closed_candles(SYMBOL, iv, limit=5, context=f"probe_{iv}")
        sha = candle_sha256(df)
        ts  = last_closed_time(df)
        print(f"  {iv:>4}  PASS  rows={len(df)}  last={ts}  sha={sha[:16]}…")
        passed += 1
    except (MarketDataError, ValidationError) as e:
        print(f"  {iv:>4}  FAIL  {e}")
        failed += 1

print("=" * 60)
print(f"  {passed}/{passed+failed} intervals PASS")

if failed:
    print("  PROBE FAIL")
    sys.exit(1)
else:
    print("  PROBE PASS")
    sys.exit(0)
