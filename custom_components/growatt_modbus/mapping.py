
from __future__ import annotations
import os, yaml, logging
from typing import Any
_LOGGER = logging.getLogger(__name__)

def embedded_path() -> str:
    return os.path.join(os.path.dirname(__file__), "map.yaml")

def resolve_mapping_path(path: str | None) -> str:
    if not path or str(path).strip().upper() == "EMBEDDED" or str(path).strip() == "":
        return embedded_path()
    given = str(path).strip()
    if os.path.exists(given):
        return given
    _LOGGER.warning("Mapping not found at %s, falling back to embedded", given)
    return embedded_path()

def load_register_mapping(path: str | None) -> dict[str, Any]:
    use_path = resolve_mapping_path(path)
    try:
        with open(use_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        sensors = data.get("sensors", []) or []
        controls = data.get("controls", []) or []
        _LOGGER.info("Mapping loaded from %s: %s sensors, %s controls", use_path, len(sensors), len(controls))
        return {"sensors": sensors, "controls": controls, "path": use_path}
    except Exception as e:
        _LOGGER.error("Failed to read mapping from %s: %s", use_path, e)
        return {"sensors": [], "controls": [], "path": use_path}
