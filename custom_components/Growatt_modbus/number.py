
from __future__ import annotations
from typing import Any, Optional
from homeassistant.components.number import NumberEntity, NumberMode
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
    data = hass.data[DOMAIN][entry.entry_id]; coord: GrowattModbusCoordinator = data["coordinator"]
    entities = []
    for c in data.get("controls", []):
        if c.get("type") == "number":
            entities.append(GrowattModbusNumber(coord, entry, c))
        elif c.get("type") == "number32":
            entities.append(GrowattModbusNumber32(coord, entry, c))
    _LOGGER.info("Adding %s number entities", len(entities))
    if entities: async_add_entities(entities)

class GrowattModbusNumber(CoordinatorEntity[dict[str, Any]], NumberEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator: GrowattModbusCoordinator, entry: ConfigEntry, cfg: dict[str, Any]) -> None:
        super().__init__(coordinator); self._coordinator = coordinator; self._entry = entry; self._cfg = cfg
        self._address = int(cfg["address"])
        self._attr_name = cfg.get("name")
        uid = cfg.get("unique_id") or f"number_{self._address}"
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_device_info = build_device_info(entry)
        self._attr_native_min_value = float(cfg.get("min", 0)); self._attr_native_max_value = float(cfg.get("max", 100))
        self._attr_native_step = float(cfg.get("step", 1)); self._attr_mode = NumberMode.SLIDER if cfg.get("mode", "slider") == "slider" else NumberMode.BOX
        self._attr_native_unit_of_measurement = cfg.get("unit_of_measurement")
        self._write_factor = float(cfg.get("write_factor", 1.0))
        self._read_uid: Optional[str] = cfg.get("read_unique_id"); self._read_factor = float(cfg.get("read_factor", 1.0))
        self._value: float = self._attr_native_min_value; self._sync_from_sensor()
    @property
    def native_value(self) -> float: return self._value
    async def async_set_native_value(self, value: float) -> None:
        step = self._attr_native_step or 1.0; minv = self._attr_native_min_value; maxv = self._attr_native_max_value
        v = max(minv, min(maxv, round(value / step) * step)); raw = int(round(v * self._write_factor))
        ok = await self._coordinator.write_single_register(self._address, raw)
        if ok:
            self._value = v; self.async_write_ha_state()
            await self._coordinator.async_request_refresh()
    def _sync_from_sensor(self) -> None:
        if not self._read_uid: return
        raw = (self._coordinator.data or {}).get(self._read_uid)
        if raw is None: return
        try:
            val = float(raw) * self._read_factor
            step = self._attr_native_step or 1.0; minv = self._attr_native_min_value; maxv = self._attr_native_max_value
            val = max(minv, min(maxv, round(val / step) * step)); self._value = val
        except Exception: pass
    def _handle_coordinator_update(self) -> None: self._sync_from_sensor(); self.async_write_ha_state()

class GrowattModbusNumber32(CoordinatorEntity[dict[str, Any]], NumberEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator: GrowattModbusCoordinator, entry: ConfigEntry, cfg: dict[str, Any]) -> None:
        super().__init__(coordinator); self._coordinator = coordinator; self._entry = entry; self._cfg = cfg
        self._base = int(cfg["base_address"]); self._order = cfg.get("word_order", "high_low")
        self._attr_name = cfg.get("name")
        uid = cfg.get("unique_id") or f"number32_{self._base}"
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_device_info = build_device_info(entry)
        self._attr_native_min_value = float(cfg.get("min", 0)); self._attr_native_max_value = float(cfg.get("max", 4294967295))
        self._attr_native_step = float(cfg.get("step", 1)); self._attr_mode = NumberMode.BOX if cfg.get("mode", "box") == "box" else NumberMode.SLIDER
        self._value: float = 0.0
    @property
    def native_value(self) -> float: return self._value
    async def async_set_native_value(self, value: float) -> None:
        v = int(max(self._attr_native_min_value, min(self._attr_native_max_value, round(value))))
        ok = await self._coordinator.write_u32(self._base, v, self._order)
        if ok:
            self._value = float(v); self.async_write_ha_state()
            await self._coordinator.async_request_refresh()
