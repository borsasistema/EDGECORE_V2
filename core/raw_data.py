"""
EDGECORE_V2 — Immutable Raw Data Layer
"""

from __future__ import annotations
import hashlib, os


class ImmutableViolation(Exception):
    pass


def _sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sidecar(path: str) -> str:
    return path + ".sha256"


def write_raw(
    filepath: str,
    content: str,
    overwrite: bool = False,
    justification: str = "",
) -> str:
    if os.path.exists(filepath) and not overwrite:
        raise ImmutableViolation(
            f"Raw data file already exists: {filepath}\n"
            f"Raw data is immutable. Use a new filename or pass overwrite=True."
        )
    if overwrite and not justification.strip():
        raise ValueError("overwrite=True requires a non-empty justification string.")

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    sha = _sha256_of_text(content)
    sidecar_content = sha
    if overwrite:
        sidecar_content += f"\n# OVERWRITE: {justification}"

    with open(_sidecar(filepath), "w") as f:
        f.write(sidecar_content)

    return sha


def read_raw(filepath: str, verify: bool = True) -> str:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Raw data not found: {filepath}")

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    if verify:
        sc = _sidecar(filepath)
        if os.path.exists(sc):
            with open(sc) as f:
                recorded = f.readline().strip()
            current = _sha256_of_text(content)
            if current != recorded:
                raise ImmutableViolation(
                    f"Checksum mismatch for {filepath}\n"
                    f"  recorded : {recorded}\n"
                    f"  current  : {current}"
                )
    return content


def assert_immutable(filepath: str) -> bool:
    read_raw(filepath, verify=True)
    return True
