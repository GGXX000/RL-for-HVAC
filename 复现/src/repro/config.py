from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    root = project_root()
    cfg_path = Path(path) if path else root / "configs" / "paper_reproduction.json"
    if not cfg_path.is_absolute():
        cfg_path = root / cfg_path
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    data["_config_path"] = str(cfg_path)
    data["_project_root"] = str(root)
    return data


def resolve_path(config: dict[str, Any], value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(config["_project_root"]) / path
