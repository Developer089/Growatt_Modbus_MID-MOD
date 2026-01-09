
from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_HOST, CONF_PORT
from .const import (
    DOMAIN, CONF_UNIT_ID, CONF_SCAN_INTERVAL, DEFAULT_SCAN_SECONDS,
    DEFAULT_PORT, DEFAULT_UNIT_ID, CONF_MAPPING_PATH,
    CONF_TRANSPORT, DEFAULT_TRANSPORT, CONF_BAUDRATE, DEFAULT_BAUDRATE, CONF_BYTESIZE, DEFAULT_BYTESIZE,
    CONF_PARITY, DEFAULT_PARITY, CONF_STOPBITS, DEFAULT_STOPBITS,
    CONF_ADDR_OFFSET, DEFAULT_ADDR_OFFSET,
)
from .coordinator import GrowattModbusCoordinator, RegisterDef
from .mapping import load_register_mapping
_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.SELECT, Platform.NUMBER]

async def async_setup(hass, config):
    """Allow discovery/config-flow only setup."""
    return True

def _ensure_uid(base: str | None, prefix: str, address: int) -> str:
    base = (base or "").strip()
    return base if base else f"{prefix}_{address}"

def _auto_inject_readbacks(sensors: list[dict], controls: list[dict]) -> tuple[list[dict], list[dict]]:
    for s in sensors:
        s["unique_id"] = _ensure_uid(s.get("unique_id"), "s", int(s.get("address", 0)))
    sensor_uids = {s["unique_id"] for s in sensors}
    for c in controls:
        addr = c.get("address", c.get("base_address", 0))
        c["unique_id"] = _ensure_uid(c.get("unique_id"), c.get("type","c"), int(addr))
        rtype = c.get("register_type", "holding")
        if c.get("type") == "select32":
            rb_uid = c.get("read_unique_id") or f"rb_{c['unique_id']}"
            if rb_uid not in sensor_uids:
                sensors.append({
                    "name": f"RB {c.get('name', c['unique_id'])}",
                    "unique_id": rb_uid,
                    "register_type": "holding",
                    "address": int(c["base_address"]),
                    "count": 2,
                    "scale": 1.0
                })
                sensor_uids.add(rb_uid)
            c["read_unique_id"] = rb_uid
            continue
        if rtype != "holding" or not addr:
            continue
        if not c.get("read_unique_id"):
            rb_uid = f"rb_{c['unique_id']}"
            if rb_uid not in sensor_uids:
                sensors.append({
                    "name": f"RB {c.get('name', c['unique_id'])}",
                    "unique_id": rb_uid,
                    "register_type": "holding",
                    "address": int(addr),
                    "count": 1,
                    "scale": 1.0
                })
                sensor_uids.add(rb_uid)
            c["read_unique_id"] = rb_uid
            c.setdefault("read_factor", 1.0)
    return sensors, controls

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    unit_id = entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_SECONDS))
    transport = entry.options.get(CONF_TRANSPORT, entry.data.get(CONF_TRANSPORT, DEFAULT_TRANSPORT))
    mapping_path = entry.options.get(CONF_MAPPING_PATH, entry.data.get(CONF_MAPPING_PATH, ""))
    addr_offset = entry.options.get(CONF_ADDR_OFFSET, DEFAULT_ADDR_OFFSET)
    serial_params = {
        "baudrate": entry.options.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
        "bytesize": entry.options.get(CONF_BYTESIZE, DEFAULT_BYTESIZE),
        "parity": entry.options.get(CONF_PARITY, DEFAULT_PARITY),
        "stopbits": entry.options.get(CONF_STOPBITS, DEFAULT_STOPBITS),
    }
    mapping = await hass.async_add_executor_job(load_register_mapping, mapping_path)
    sensors_cfg = list(mapping.get("sensors", []))
    controls_cfg = list(mapping.get("controls", []))
    sensors_cfg, controls_cfg = _auto_inject_readbacks(sensors_cfg, controls_cfg)
    _LOGGER.info("Growatt mapping path: %s", mapping.get("path"))
    _LOGGER.info("Growatt sensors: %s, controls: %s (after auto-readback)", len(sensors_cfg), len(controls_cfg))
    registers = [RegisterDef(**r) for r in sensors_cfg]
    coordinator = GrowattModbusCoordinator(
        hass, host, port, unit_id, registers, scan_interval,
        transport=transport, serial_params=serial_params, address_offset=addr_offset
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator, "registers": registers, "controls": controls_cfg}
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async def _svc_write_register(call: ServiceCall):
        ok = await coordinator.write_single_register(int(call.data["address"]), int(call.data["value"]))
        _LOGGER.info("write_register %s", ok)
    async def _svc_write_registers(call: ServiceCall):
        addr = int(call.data["address"])
        values = [int(v) for v in call.data["values"]]
        ok = await coordinator.write_multiple_registers(addr, values)
        _LOGGER.info("write_registers %s", ok)
    async def _svc_write_u32(call: ServiceCall):
        addr = int(call.data["address"])
        value = int(call.data["value"])
        word_order = call.data.get("word_order", "high_low")
        ok = await coordinator.write_u32(addr, value, word_order)
        _LOGGER.info("write_u32 %s", ok)
    async def _svc_log_mapping(call: ServiceCall):
        _LOGGER.info("Mapping path: %s", mapping.get("path"))
        _LOGGER.info("Sensors cfg: %s", sensors_cfg)
        _LOGGER.info("Controls cfg: %s", controls_cfg)
    hass.services.async_register(DOMAIN, "write_register", _svc_write_register)
    hass.services.async_register(DOMAIN, "write_registers", _svc_write_registers)
    hass.services.async_register(DOMAIN, "write_u32", _svc_write_u32)
    hass.services.async_register(DOMAIN, "log_mapping", _svc_log_mapping)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: GrowattModbusCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_close()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
