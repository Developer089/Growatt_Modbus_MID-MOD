
from __future__ import annotations
from typing import Any, Optional
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging
from .const import DOMAIN
from .coordinator import GrowattModbusCoordinator, RegisterDef
from .device_helper import build_device_info
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coord: GrowattModbusCoordinator = data["coordinator"]
    regs: list[RegisterDef] = data["registers"]
    entities = [GrowattRegisterSensor(coord, entry, r) for r in regs]
    _LOGGER.info("Adding %s sensor entities", len(entities))
    if entities: async_add_entities(entities)

class GrowattRegisterSensor(CoordinatorEntity[dict[str, Any]], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GrowattModbusCoordinator, entry: ConfigEntry, reg: RegisterDef) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._reg = reg
        self._options = reg.options or None  # enum map if provided
        uid = reg.unique_id or f"s_{reg.address}"
        self._attr_unique_id = f"{entry.entry_id}_{uid}"
        self._attr_name = reg.name
        self._attr_device_info = build_device_info(entry)
        self._attr_native_unit_of_measurement = reg.unit_of_measurement
        if reg.device_class:
            try:
                self._attr_device_class = SensorDeviceClass(reg.device_class)
            except Exception:
                self._attr_device_class = None
        if reg.state_class:
            try:
                self._attr_state_class = SensorStateClass(reg.state_class)
            except Exception:
                self._attr_state_class = None

    @property
    def native_value(self) -> Any:
        raw = (self.coordinator.data or {}).get(self._reg.unique_id)
        if self._options is not None and raw is not None:
            try:
                key = int(round(float(raw)))
            except Exception:
                return raw
            return self._options.get(key, str(key))
        return raw

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        raw = (self.coordinator.data or {}).get(self._reg.unique_id)
        attrs = {}
        if raw is not None:
            try:
                attrs["raw_value"] = int(round(float(raw)))
            except Exception:
                attrs["raw_value"] = raw
        if self._options is not None:
            attrs["options_map"] = self._options
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
