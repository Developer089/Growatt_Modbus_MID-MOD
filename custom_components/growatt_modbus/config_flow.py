
from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import (
    DOMAIN, CONF_UNIT_ID, CONF_SCAN_INTERVAL, DEFAULT_SCAN_SECONDS, DEFAULT_PORT, DEFAULT_UNIT_ID,
    CONF_MAPPING_PATH, CONF_TRANSPORT, DEFAULT_TRANSPORT,
    CONF_BAUDRATE, DEFAULT_BAUDRATE, CONF_BYTESIZE, DEFAULT_BYTESIZE,
    CONF_PARITY, DEFAULT_PARITY, CONF_STOPBITS, DEFAULT_STOPBITS,
    CONF_ADDR_OFFSET, DEFAULT_ADDR_OFFSET, MIN_SCAN_SECONDS, MAX_SCAN_SECONDS,
)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): int,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_SECONDS): vol.All(
        vol.Coerce(int), vol.Range(min=MIN_SCAN_SECONDS, max=MAX_SCAN_SECONDS)
    ),
    vol.Optional(CONF_MAPPING_PATH, default="EMBEDDED"): str,
})

class GrowattModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=f"Growatt MOD/MID Modbus TCP @ {user_input[CONF_HOST]}", data=user_input)
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GrowattModbusOptionsFlow(config_entry)

class GrowattModbusOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.config_entry = entry

    def _entry_default(self, key: str, fallback: Any) -> Any:
        return self.config_entry.options.get(key, self.config_entry.data.get(key, fallback))

    def _entry_int_default(self, key: str, fallback: int) -> int:
        value = self._entry_default(key, fallback)
        if value is None or str(value).strip() == "":
            return fallback
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _options_schema(self) -> vol.Schema:
        transport = str(self._entry_default(CONF_TRANSPORT, DEFAULT_TRANSPORT)).lower()
        if transport not in {"tcp", "rtutcp"}:
            transport = DEFAULT_TRANSPORT
        parity = str(self._entry_default(CONF_PARITY, DEFAULT_PARITY)).upper()
        if parity not in {"N", "E", "O"}:
            parity = DEFAULT_PARITY
        mapping_path = self._entry_default(CONF_MAPPING_PATH, "EMBEDDED")
        mapping_path = mapping_path if str(mapping_path).strip() else "EMBEDDED"
        return vol.Schema({
            vol.Optional(CONF_SCAN_INTERVAL, default=self._entry_int_default(CONF_SCAN_INTERVAL, DEFAULT_SCAN_SECONDS)): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_SECONDS, max=MAX_SCAN_SECONDS)
            ),
            vol.Optional(CONF_MAPPING_PATH, default=mapping_path): str,
            vol.Optional(CONF_TRANSPORT, default=transport): vol.In(["tcp", "rtutcp"]),
            vol.Optional(CONF_ADDR_OFFSET, default=self._entry_int_default(CONF_ADDR_OFFSET, DEFAULT_ADDR_OFFSET)): vol.Coerce(int),
            vol.Optional(CONF_BAUDRATE, default=self._entry_int_default(CONF_BAUDRATE, DEFAULT_BAUDRATE)): vol.Coerce(int),
            vol.Optional(CONF_BYTESIZE, default=self._entry_int_default(CONF_BYTESIZE, DEFAULT_BYTESIZE)): vol.Coerce(int),
            vol.Optional(CONF_PARITY, default=parity): vol.In(["N", "E", "O"]),
            vol.Optional(CONF_STOPBITS, default=self._entry_int_default(CONF_STOPBITS, DEFAULT_STOPBITS)): vol.Coerce(int),
        })
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=self._options_schema())
