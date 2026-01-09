
from __future__ import annotations
from typing import Any, Optional
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging
from .const import DOMAIN
from .coordinator import GrowattModbusCoordinator
from .device_helper import build_device_info
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coord: GrowattModbusCoordinator = data["coordinator"]
    entities = [GrowattModbusSwitch(coord, entry, c) for c in data.get("controls", []) if c.get("type") == "switch"]
    _LOGGER.info("Adding %s switch entities", len(entities))
    if entities: async_add_entities(entities)

class GrowattModbusSwitch(CoordinatorEntity[dict[str, Any]], SwitchEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator: GrowattModbusCoordinator, entry: ConfigEntry, cfg: dict[str, Any]) -> None:
        super().__init__(coordinator); self._coordinator = coordinator; self._entry = entry; self._cfg = cfg
        self._register_type = cfg.get("register_type", "holding"); self._address = int(cfg["address"])
        self._on = int(cfg.get("on_value", 1)); self._off = int(cfg.get("off_value", 0))
        self._state: Optional[bool] = None
        self._attr_name = cfg.get("name")
        uid = cfg.get("unique_id") or f"switch_{self._address}"
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_device_info = build_device_info(entry)
        self._read_uid: Optional[str] = cfg.get("read_unique_id"); self._read_factor: float = float(cfg.get("read_factor", 1.0))
        self._sync_from_sensor()
    @property
    def is_on(self) -> bool | None: return self._state
    async def async_turn_on(self, **kwargs):
        ok = await self._write(self._on); 
        if ok: self._state = True; self.async_write_ha_state()
    async def async_turn_off(self, **kwargs):
        ok = await self._write(self._off);
        if ok: self._state = False; self.async_write_ha_state()
    async def _write(self, value: int) -> bool:
        ok = await (self._coordinator.write_coil(self._address, value) if self._register_type == "coil" else self._coordinator.write_single_register(self._address, value))
        if ok: await self._coordinator.async_request_refresh()
        return ok
    def _sync_from_sensor(self) -> None:
        if not self._read_uid: return
        raw = (self._coordinator.data or {}).get(self._read_uid)
        if raw is None: return
        try:
            v = int(round(float(raw) / self._read_factor)); self._state = (v == self._on)
        except Exception: pass
    def _handle_coordinator_update(self) -> None: self._sync_from_sensor(); self.async_write_ha_state()
