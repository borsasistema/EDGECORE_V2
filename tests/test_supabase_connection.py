"""
EDGECORE_V2 — Supabase Connection Test
Run: python tests/test_supabase_connection.py
"""

import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from core.supabase_client import get_client, health_check

TEST_RUN_ID = f"test_faz0b_{uuid.uuid4().hex[:12]}"
NOW         = datetime.now(timezone.utc).isoformat()
RESULTS     = {}
client      = None
inserted    = False


def check(name: str, ok: bool, msg: str = "") -> None:
    RESULTS[name] = ok
    status = "PASS" if ok else "FAIL"
    print(f"  {name:<30} {status}" + (f"  — {msg}" if msg and not ok else ""))
    if not ok:
        raise SystemExit(1)


# ── 1. SUPABASE_CONNECT ───────────────────────────────────────────────────────
print(f"\nEDGECORE_V2  FAZ 0B — Supabase Connection Test")
print(f"UTC now  : {NOW}")
print(f"run_id   : {TEST_RUN_ID}")
print("=" * 55)
print()

try:
    client = get_client()
    health_check(client)
    check("SUPABASE_CONNECT", True)
except Exception as e:
    check("SUPABASE_CONNECT", False, str(e))


# ── 2. INSERT ─────────────────────────────────────────────────────────────────
try:
    payload = {
        "project_id":     "EDGECORE_V2",
        "run_id":         TEST_RUN_ID,
        "engine_version": "0.1.0",
        "git_commit":     "faz0b_test",
        "data_version":   "v1",
        "test_name":      "test_supabase_connection",
        "status":         "PASS",
        "input_sha256":   None,
        "output_sha256":  None,
        "started_at":     NOW,
        "finished_at":    NOW,
        "metadata":       {"source": "faz0b_connection_test"},
    }
    resp = client.table("v2_runs").insert(payload).execute()
    assert resp.data and len(resp.data) == 1, "INSERT returned no data"
    inserted = True
    check("INSERT", True)
except Exception as e:
    check("INSERT", False, str(e))


# ── 3. READ_VERIFY ────────────────────────────────────────────────────────────
try:
    resp = (
        client.table("v2_runs")
        .select("*")
        .eq("run_id", TEST_RUN_ID)
        .execute()
    )
    assert resp.data and len(resp.data) == 1, "READ returned no row"
    row = resp.data[0]
    assert row["project_id"]     == "EDGECORE_V2",              "project_id mismatch"
    assert row["run_id"]         == TEST_RUN_ID,                 "run_id mismatch"
    assert row["engine_version"] == "0.1.0",                     "engine_version mismatch"
    assert row["status"]         == "PASS",                      "status mismatch"
    assert row["test_name"]      == "test_supabase_connection",  "test_name mismatch"
    check("READ_VERIFY", True)
except Exception as e:
    check("READ_VERIFY", False, str(e))


# ── 4. DELETE_CLEANUP ─────────────────────────────────────────────────────────
try:
    if inserted and client:
        resp = (
            client.table("v2_runs")
            .delete()
            .eq("run_id", TEST_RUN_ID)
            .execute()
        )
    check("DELETE_CLEANUP", True)
except Exception as e:
    check("DELETE_CLEANUP", False, str(e))


# ── Final report ──────────────────────────────────────────────────────────────
print()
print("=" * 55)
all_pass = all(RESULTS.values())
for k, v in RESULTS.items():
    print(f"  {k:<30} {'PASS' if v else 'FAIL'}")
print()
print(f"  OVERALL : {'PASS' if all_pass else 'FAIL'}")
sys.exit(0 if all_pass else 1)
