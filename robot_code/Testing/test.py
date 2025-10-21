# Requires: pip install bleak
import asyncio
from bleak import BleakScanner



async def find_all_devices(): # SK-DB82
    print("Scanning 8 seconds...")
    devices = await BleakScanner.discover(timeout=8.0)
    for d in devices:
        if d.name is None:  
            continue
        print(d.name)
        if "SM-" in (d.name or "") or "Sphero" in (d.name or ""):
            print("Possible Mini ->", d.name, d.address)
    print(f"Found {len(devices)} devices total")

#find_all_devices()


#!/usr/bin/env python3
"""
Drive Sphero Mini named 'SK-DB82', show heading, and print sensor events.

Run:
  python mini_drive_and_telemetry.py
"""

import time
from datetime import datetime

from spherov2 import scanner
from spherov2.sphero_edu import SpheroEduAPI, EventType
from spherov2.types import Color


NAME = "SK-DB82"   # ← your Mini's BLE name


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def main():
    # 1) Find THIS specific Mini
    log(f"Looking for {NAME!r} ... (wake it, be ~1m away)")
    toys = scanner.find_toys(toy_names=[NAME])
    if not toys:
        log(f"Could not find the toy named {NAME}. Is it awake and nearby?")
        return
    toy = toys[0]

    if toy is None:
        log("Could not find the toy. Is it awake / nearby?")
        return

    log(f"Found: name={toy.name} addr={getattr(toy, 'address', 'n/a')}")

    # 2) Connect using the high-level Sphero Edu API
    with SpheroEduAPI(toy) as api:
        log("Connected!")

        # ---------- Register useful event callbacks ----------
        # Note: These are the events the high-level API exposes.
        # Each will be invoked on a background thread when it happens.
        def on_collision(_api):
            log("EVENT: collision")
            _api.set_main_led(Color(255, 0, 0))

        def on_freefall(_api):
            log("EVENT: freefall")
            _api.set_main_led(Color(0, 0, 255))

        def on_landing(_api):
            log("EVENT: landing")
            _api.set_main_led(Color(0, 255, 0))

        def on_gyro_max(_api):
            log("EVENT: gyro max")

        def on_charging(_api):
            log("EVENT: charging")

        def on_not_charging(_api):
            log("EVENT: not charging")

        api.register_event(EventType.on_collision, on_collision)
        api.register_event(EventType.on_freefall, on_freefall)
        api.register_event(EventType.on_landing, on_landing)
        api.register_event(EventType.on_gyro_max, on_gyro_max)
        api.register_event(EventType.on_charging, on_charging)
        api.register_event(EventType.on_not_charging, on_not_charging)

        # ---------- LED hello ----------
        api.set_main_led(Color(255, 255, 255))  # white
        time.sleep(0.2)
        api.set_main_led(Color(0, 180, 255))    # cyan
        time.sleep(0.2)
        api.set_main_led(Color(255, 40, 120))   # pink

        # ---------- Aim & heading ----------
        # "Aim" sets the robot's idea of "forward" (0°). You can also just call reset_aim().
        api.reset_aim()
        log(f"Initial heading = {api.get_heading()}°")

        # ---------- Drive pattern: a lit-up square + a spin ----------
        speed = 90  # 0..255 (Mini likes ~60-120 indoors)
        segment = 1.0

        for heading in (0, 90, 180, 270):
            api.set_main_led(Color(255, 255 - heading % 255, heading % 255))
            # roll() lets you specify heading, speed, duration directly
            api.roll(heading=heading, speed=speed, duration=segment)
            log(f"Rolling heading={heading} speed={speed} for {segment}s")
            # Brief stop between legs
            api.stop_roll()
            time.sleep(0.2)
            log(f"Current heading reported = {api.get_heading()}°")

        # Spin in place (fun way to trigger gyro events)
        log("Spinning 360° in 1.5s")
        api.spin(360, 1.5)
        api.stop_roll()

        # ---------- Passive telemetry loop ----------
        # The SpheroEdu API exposes heading directly. Other raw sensors are surfaced via events.
        # We poll heading for a bit so you can move the robot and watch values & events flow in.
        log("Telemetry: polling heading for ~10 seconds (also watching events)...")
        t_end = time.time() + 10
        while time.time() < t_end:
            h = api.get_heading()
            print(f"  heading={h:3d}°", end="\r", flush=True)
            time.sleep(0.1)

        api.set_main_led(Color(0, 0, 0))
        api.stop_roll()
        log("Done. Disconnecting...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted by user.")
