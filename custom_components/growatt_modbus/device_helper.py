
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
def build_device_info(entry):
    host = entry.data.get(CONF_HOST)
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Growatt MOD/MID Modbus",
        manufacturer="Growatt",
        model="MOD/MID",
        configuration_url=(f"http://{host}" if host else None)
    )
