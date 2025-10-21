# Requires: pip install bleak
import asyncio
from bleak import BleakScanner

async def go():
    print("Scanning 8 seconds...")
    devices = await BleakScanner.discover(timeout=8.0)
    for d in devices:
        if "SM-" in (d.name or "") or "Sphero" in (d.name or ""):
            print("Possible Mini ->", d.name, d.address)
    print(f"Found {len(devices)} devices total")

asyncio.run(go())
