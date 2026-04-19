from __future__ import annotations
import yaml
from pathlib import Path
from typing import Any, Dict


def load_sports_config(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def get_sport_cfg(cfg: Dict[str, Any], sport_name: str) -> Dict[str, Any]:
    sports = cfg.get("sports") or {}
    sport = sports.get(sport_name)
    if not sport:
        raise KeyError(f"Sport '{sport_name}' not found in config")
    return sport
