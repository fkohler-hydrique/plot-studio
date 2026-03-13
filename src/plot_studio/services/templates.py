"""Template persistence helpers."""

import json
from pathlib import Path
from typing import Any

from plot_studio.config import SAVED_CONFIGS_FILE


def load_saved_configs_from_disk(
    path: str | Path = SAVED_CONFIGS_FILE,
) -> list[dict[str, Any]]:
    """Load saved plot templates from disk."""
    config_path = Path(path)
    if not config_path.exists():
        return []

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def persist_saved_configs_to_disk(
    saved_configs: list[dict[str, Any]],
    path: str | Path = SAVED_CONFIGS_FILE,
) -> None:
    """Persist saved plot templates to disk."""
    config_path = Path(path)
    try:
        config_path.write_text(
            json.dumps(saved_configs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        return
