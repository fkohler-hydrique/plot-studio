import json
import shutil
import uuid
from pathlib import Path

from plot_studio.services.templates import (
    load_saved_configs_from_disk,
    persist_saved_configs_to_disk,
)


def make_workspace_temp_dir() -> Path:
    temp_dir = Path("tests") / "_tmp" / str(uuid.uuid4())
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def test_template_persistence_round_trip():
    temp_dir = make_workspace_temp_dir()
    try:
        config_path = temp_dir / "saved_configs.json"
        configs = [{"id": "cfg-1", "name": "Main dashboard", "plots": []}]

        persist_saved_configs_to_disk(configs, config_path)

        loaded = load_saved_configs_from_disk(config_path)
        assert loaded == configs
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_load_saved_configs_filters_non_dict_items():
    temp_dir = make_workspace_temp_dir()
    try:
        config_path = temp_dir / "saved_configs.json"
        config_path.write_text(
            json.dumps([{"id": "cfg-1"}, "bad-entry", 42]),
            encoding="utf-8",
        )

        loaded = load_saved_configs_from_disk(config_path)
        assert loaded == [{"id": "cfg-1"}]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
