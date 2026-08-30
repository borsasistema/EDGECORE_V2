"""
TEST 001 — Configuration
LOCKED. Do not change thresholds.
"""
from datetime import timezone

PROJECT_ID   = "EDGECORE_V2"
TEST_ID      = "TEST_001"
UTC          = timezone.utc

# ── Period ────────────────────────────────────────────────────────────────────
FULL_START   = "2025-09-01"
FULL_END     = "2026-08-29"
SMOKE_DAYS   = 7          # smoke run: first N days only

EVAL_HOUR    = 0
EVAL_MINUTE  = 5          # 00:05 UTC daily snapshot

# ── Universe filters (V1 exact) ───────────────────────────────────────────────
VOLUME_MIN_USD   = 5_000_000
ATR_MIN          = 1.3
EMA_GAP_MIN      = 1.0
KLINES_1H_LIMIT  = 200     # history window for ATR / EMA-gap

# ── TP / SL ───────────────────────────────────────────────────────────────────
TP_PCT  = 2.0   # +2%
SL_PCT  = 1.0   # -1%

# ── Path ─────────────────────────────────────────────────────────────────────
PATH_MINUTES = 1440        # 24 hours of 1m candles

# ── Horizons (hours) ──────────────────────────────────────────────────────────
HORIZONS_H = [1, 4, 8, 24]

# ── Bootstrap ─────────────────────────────────────────────────────────────────
BOOTSTRAP_N = 1_000
BOOTSTRAP_SEED = 42

# ── Stable coins (excluded from universe) ────────────────────────────────────
STABLE_LIST = {
    "USDT","USDC","BUSD","TUSD","USDP","DAI","FDUSD","PYUSD",
    "USDD","GUSD","FRAX","LUSD","SUSD","ALUSD","CUSD","HUSD",
    "EURS","XAUT","PAXG","USTC",
}

# ── Censor threshold warning ──────────────────────────────────────────────────
CENSOR_WARN_PCT = 5.0      # warn if censor rate > 5%
