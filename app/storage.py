from __future__ import annotations

import os
from pathlib import Path

from .models import AppState

_DATA_FILE = Path(os.environ.get("DATA_FILE", "data/ledger.json"))


def load() -> AppState:
    if not _DATA_FILE.exists():
        return AppState()
    try:
        return AppState.model_validate_json(_DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RuntimeError(f"Failed to load ledger data: {e}") from e


def save(state: AppState) -> None:
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _DATA_FILE.with_suffix(".tmp")
    tmp.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(_DATA_FILE)
