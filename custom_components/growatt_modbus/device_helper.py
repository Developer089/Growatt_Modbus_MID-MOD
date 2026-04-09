
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME

def build_device_info(entry):
    host = entry.data.get(CONF_HOST)
    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME)
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=device_name,
        manufacturer="Growatt",
        model="MOD/MID",
        configuration_url=(f"http://{host}" if host else None)
    )
