
from __future__ import annotations
from typing import Final

DOMAIN: Final = "growatt_modbus"

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_UNIT_ID: Final = "unit_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_MAPPING_PATH: Final = "mapping_path"
CONF_TRANSPORT: Final = "transport"
CONF_BAUDRATE: Final = "baudrate"
CONF_BYTESIZE: Final = "bytesize"
CONF_PARITY: Final = "parity"
CONF_STOPBITS: Final = "stopbits"
CONF_ADDR_OFFSET: Final = "address_offset"

DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1
DEFAULT_SCAN_SECONDS: Final = 10
DEFAULT_TRANSPORT: Final = "tcp"
DEFAULT_ADDR_OFFSET: Final = 0

DEFAULT_BAUDRATE: Final = 9600
DEFAULT_BYTESIZE: Final = 8
DEFAULT_PARITY: Final = "N"
DEFAULT_STOPBITS: Final = 1
