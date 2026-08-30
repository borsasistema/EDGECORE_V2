"""
EDGECORE_V2 — Core Constants
PROJECT_ID : EDGECORE_V2
"""

from datetime import timezone
import os

PROJECT_ID   = "EDGECORE_V2"
DATA_VERSION = "v1"

UTC = timezone.utc

CLOSED_CANDLE_ONLY = True

VALID_INTERVALS = ("1m", "5m", "15m", "1h", "4h", "1d")

FEE_RT     = 0.001
FEE_RT_PCT = 0.10

assert abs(FEE_RT * 100 - FEE_RT_PCT) < 1e-9
assert 1.8 < (2.0 - FEE_RT * 100) < 2.0
assert 1.0 < (1.0 + FEE_RT * 100) < 1.2

_ROOT              = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_RAW_DIR       = os.path.join(_ROOT, "data", "raw")
DATA_PROCESSED_DIR = os.path.join(_ROOT, "data", "processed")
DATA_RESULTS_DIR   = os.path.join(_ROOT, "data", "results")
