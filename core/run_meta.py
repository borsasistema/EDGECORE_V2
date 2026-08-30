"""
EDGECORE_V2 — Run & Version Metadata
"""

from __future__ import annotations
import hashlib, json, os, platform, sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any

PROJECT_ID = "EDGECORE_V2"
VERSION    = "0.1.0"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class RunMeta:
    run_id:      str
    description: str
    created_at:  str             = field(default_factory=_utc_now_iso)
    project_id:  str             = PROJECT_ID
    version:     str             = VERSION
    python:      str             = field(default_factory=lambda: sys.version.split()[0])
    platform:    str             = field(default_factory=platform.system)
    params:      Dict[str, Any]  = field(default_factory=dict)
    input_files: Dict[str, Any]  = field(default_factory=dict)
    notes:       str             = ""

    def add_input_file(self, name: str, path: str) -> "RunMeta":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Input file not found: {path}")
        self.input_files[name] = {
            "path":   path,
            "sha256": _sha256(path),
            "size":   os.path.getsize(path),
        }
        return self

    def verify_inputs(self) -> bool:
        for name, info in self.input_files.items():
            if not os.path.exists(info["path"]):
                raise RuntimeError(f"Input file missing: {name} → {info['path']}")
            current = _sha256(info["path"])
            if current != info["sha256"]:
                raise RuntimeError(
                    f"Input file modified since run was recorded: {name}\n"
                    f"  recorded : {info['sha256']}\n"
                    f"  current  : {current}"
                )
        return True

    def save(self, results_dir: str) -> str:
        os.makedirs(results_dir, exist_ok=True)
        filename = f"meta_{self.run_id}_{self.created_at[:10]}.json"
        filepath = os.path.join(results_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        return filepath

    @classmethod
    def load(cls, filepath: str) -> "RunMeta":
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
