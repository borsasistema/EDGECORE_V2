"""
EDGECORE_V2 — Supabase Client
"""

from __future__ import annotations
import os
from supabase import create_client, Client


class SupabaseConfigError(Exception):
    pass


def _get_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise SupabaseConfigError(
            f"Environment variable '{key}' is not set or empty. "
            f"Set it before running EDGECORE_V2."
        )
    return val


def get_client() -> Client:
    url = _get_env("SUPABASE_URL")
    key = _get_env("SUPABASE_KEY")
    return create_client(url, key)


def health_check(client: Client) -> bool:
    """
    Verify connectivity by reading one row from v2_runs.
    Raises on connection failure. Returns True on success.
    """
    try:
        response = (
            client.table("v2_runs")
            .select("id")
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise RuntimeError(
            f"Supabase health check failed — cannot reach v2_runs: {e}"
        ) from e

    if hasattr(response, "error") and response.error:
        raise RuntimeError(
            f"Supabase health check error: {response.error}"
        )

    return True
