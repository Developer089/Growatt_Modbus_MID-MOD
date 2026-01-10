
from __future__ import annotations
import asyncio, logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, DefaultDict, Optional
from collections import defaultdict
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
_LOGGER = logging.getLogger(__name__)

try:
    from pymodbus.client import AsyncModbusTcpClient, AsyncModbusSerialClient
except Exception as exc:
    _LOGGER.error("pymodbus import failed: %s", exc); raise

@dataclass
class RegisterDef:
    name: str
    unique_id: str
    register_type: str  # "input" or "holding"
    address: int
    count: int = 1
    scale: float = 1.0
    unit_of_measurement: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    signed: bool = False
    options: dict[int, str] | None = None  # enum mapping for sensor (0->"text")

class GrowattModbusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    First cycle after startup: HOLDING registers are read FIRST (one-time).
    Next cycles: only INPUTs are polled; holdings come from cache.
    Writes update cache immediately (16b & 32b) and trigger UI refresh.
    """
    def __init__(self, hass: HomeAssistant, host: str, port: int, unit_id: int, registers, scan_interval: int, transport="tcp", serial_params=None, address_offset: int = 0) -> None:
        super().__init__(hass, _LOGGER, name="growatt_modbus coordinator", update_interval=timedelta(seconds=scan_interval))
        self._host, self._port, self._unit_id = host, port, unit_id
        self._registers: List[RegisterDef] = registers; self._transport = (transport or "tcp").lower()
        self._serial_params = serial_params or {}; self._client = None; self._lock = asyncio.Lock()
        self._addr_off = int(address_offset or 0)

        self._hold_once_done = False
        self._hold_cache: Dict[str, Any] = {}
        self._hold_regs_by_addr: DefaultDict[int, List[RegisterDef]] = defaultdict(list)
        for r in self._registers:
            if r.register_type == "holding":
                self._hold_regs_by_addr[int(r.address)].append(r)

    def _addr(self, addr: int) -> int: return int(addr) - self._addr_off if self._addr_off else int(addr)

    async def _ensure_client(self):
        if self._client is None:
            if self._transport == "rtutcp":
                url = f"socket://{self._host}:{self._port}"
                params = {"method":"rtu","port":url,"baudrate":int(self._serial_params.get("baudrate",9600)),"bytesize":int(self._serial_params.get("bytesize",8)),"parity":str(self._serial_params.get("parity","N")),"stopbits":int(self._serial_params.get("stopbits",1)),"timeout":5}
                self._client = AsyncModbusSerialClient(**params)
            else:
                try: self._client = AsyncModbusTcpClient(self._host, port=self._port, timeout=5)
                except TypeError: self._client = AsyncModbusTcpClient(self._host, port=self._port)
        if not bool(getattr(self._client, "connected", False)):
            try: res = await self._client.connect()
            except Exception as e: raise UpdateFailed(f"Modbus connect failed: {e}") from e
        return self._client

    async def _async_update_data(self) -> dict[str, Any]:
        async with self._lock:
            try:
                result: dict[str, Any] = {}
                inputs = [r for r in self._registers if r.register_type == "input"]
                holdings = [r for r in self._registers if r.register_type == "holding"]

                # First cycle: read HOLDINGS FIRST, then inputs
                if not self._hold_once_done and holdings:
                    _LOGGER.info("First cycle: reading HOLDING registers first")
                    await self._read_grouped(holdings, result, self._read_holding)
                    for r in holdings:
                        self._hold_cache[r.unique_id] = result.get(r.unique_id)
                    self._hold_once_done = True

                    if inputs:
                        await self._read_grouped(inputs, result, self._read_input)
                else:
                    # Later cycles: inputs only; holdings from cache
                    if inputs:
                        await self._read_grouped(inputs, result, self._read_input)
                    for r in holdings:
                        result[r.unique_id] = self._hold_cache.get(r.unique_id)

                return result
            except Exception as err:
                raise UpdateFailed(err) from err

    async def _read_grouped(self, regs: list[RegisterDef], out: dict[str, Any], fn):
        regs = sorted(regs, key=lambda r: r.address)
        GAP = 4; start=None; end=None; acc=[]
        for r in regs:
            if start is None: start=r.address; end=r.address+r.count; acc=[r]; continue
            if r.address <= end+GAP: end=max(end, r.address+r.count); acc.append(r)
            else: await self._read_window(fn, out, start, end, acc); start=r.address; end=r.address+r.count; acc=[r]
        if start is not None: await self._read_window(fn, out, start, end, acc)

    async def _read_window(self, fn, out, start, end, regs):
        raw = await fn(self._addr(start), end-start)
        for r in regs:
            val=None
            if raw:
                off = r.address-start; chunk = raw[off:off+r.count]
                if len(chunk) >= r.count:
                    if r.count==1:
                        v=chunk[0]; 
                        if r.signed and v>=0x8000: v-=0x10000
                        val = v * r.scale
                    elif r.count==2:
                        high,low=chunk[0],chunk[1]; v=(high<<16)|low
                        if r.signed and v>=0x80000000: v-=0x100000000
                        val = v * r.scale
            out[r.unique_id]=val

    async def _call_read(self, method_name, address, count):
        client = await self._ensure_client(); method = getattr(client, method_name)
        a = self._addr(address)
        for args in ((a, count, self._unit_id), (a, count)):
            try: return await method(*args)
            except TypeError:
                try: return await method(address=a, count=count, unit=self._unit_id)
                except TypeError:
                    try: return await method(address=a, count=count)
                    except TypeError: continue
        return None

    async def _read_input(self, address, count):
        rr = await self._call_read("read_input_registers", address, count)
        return None if rr is None or (getattr(rr,"isError",None) and rr.isError()) else getattr(rr,"registers",None)

    async def _read_holding(self, address, count):
        rr = await self._call_read("read_holding_registers", address, count)
        return None if rr is None or (getattr(rr,"isError",None) and rr.isError()) else getattr(rr,"registers",None)

    async def write_single_register(self, address: int, value: int) -> bool:
        a=self._addr(address); client=await self._ensure_client()
        for variant in (lambda: client.write_register(a,value,self._unit_id), lambda: client.write_register(address=a,value=value,unit=self._unit_id), lambda: client.write_register(a,value), lambda: client.write_register(address=a,value=value)):
            try:
                rr = await variant()
                if getattr(rr,"isError",lambda: False)(): continue
                # update cache for 16-bit sensors at this address
                for r in self._hold_regs_by_addr.get(int(address), []):
                    if r.count == 1:
                        self._hold_cache[r.unique_id] = (value * r.scale)
                await self.async_request_refresh()
                return True
            except TypeError: continue
            except Exception: return False
        return False

    async def write_multiple_registers(self, address: int, values: list[int]) -> bool:
        a=self._addr(address); client=await self._ensure_client()
        for variant in (lambda: client.write_registers(a,values,self._unit_id),
                        lambda: client.write_registers(address=a, values=values, unit=self._unit_id),
                        lambda: client.write_registers(a,values),
                        lambda: client.write_registers(address=a, values=values)):
            try:
                rr = await variant()
                if getattr(rr,"isError",lambda: False)(): continue

                # 16b cache updates
                for i, val in enumerate(values):
                    addr_i = address + i
                    for r in self._hold_regs_by_addr.get(addr_i, []):
                        if r.count == 1:
                            self._hold_cache[r.unique_id] = (val * r.scale)

                # 32b cache update at base address if two or more values provided
                if len(values) >= 2:
                    hi, lo = values[0] & 0xFFFF, values[1] & 0xFFFF
                    u32 = ((hi << 16) | lo)
                    for r in self._hold_regs_by_addr.get(int(address), []):
                        if r.count == 2:
                            self._hold_cache[r.unique_id] = (u32 * r.scale)

                await self.async_request_refresh()
                return True
            except TypeError: continue
            except Exception: return False
        return False

    async def write_u32(self, base_address: int, value: int, word_order: str = "high_low") -> bool:
        v = int(value) & 0xFFFFFFFF
        hi = (v >> 16) & 0xFFFF; lo = v & 0xFFFF
        values = [hi, lo] if word_order == "high_low" else [lo, hi]
        ok = await self.write_multiple_registers(base_address, values)
        if ok:
            for r in self._hold_regs_by_addr.get(int(base_address), []):
                if r.count == 2:
                    self._hold_cache[r.unique_id] = (v * r.scale)
        return ok

    async def write_coil(self, address: int, value: int) -> bool:
        a = self._addr(address); client = await self._ensure_client()
        for variant in (lambda: client.write_coil(a, bool(value), self._unit_id),
                        lambda: client.write_coil(address=a, value=bool(value), unit=self._unit_id),
                        lambda: client.write_coil(a, bool(value)),
                        lambda: client.write_coil(address=a, value=bool(value))):
            try:
                rr = await variant()
                if getattr(rr,"isError",lambda: False)(): continue
                await self.async_request_refresh()
                return True
            except TypeError: continue
            except Exception: return False
        return False

    async def async_close(self):
        try:
            if self._client:
                await self._client.close()
        except Exception:
            pass
