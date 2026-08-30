"""EDGECORE_V2 core — shared by research/ and production/."""
from .constants import PROJECT_ID, UTC, FEE_RT, FEE_RT_PCT, VALID_INTERVALS
from .validator  import validate_ohlcv, validate_signal_list, fee_assertion, ValidationError
from .run_meta   import RunMeta
from .raw_data   import write_raw, read_raw, assert_immutable, ImmutableViolation

__all__ = [
    "PROJECT_ID", "UTC", "FEE_RT", "FEE_RT_PCT", "VALID_INTERVALS",
    "validate_ohlcv", "validate_signal_list", "fee_assertion", "ValidationError",
    "RunMeta",
    "write_raw", "read_raw", "assert_immutable", "ImmutableViolation",
]
