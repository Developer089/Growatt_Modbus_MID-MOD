from __future__ import annotations
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST
from .const import DOMAIN

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    config = dict(entry.data)
    if CONF_HOST in config:
        config[CONF_HOST] = "**REDACTED**"
    options = dict(entry.options)

    return {
        "config": config,
        "options": options,
        "coordinator": {
            "available": coordinator.available,
            "register_count": len(coordinator._registers),
            "holding_cache_size": len(coordinator._hold_cache),
        },
        "data": {
            k: v for k, v in (coordinator.data or {}).items()
        },
    }
