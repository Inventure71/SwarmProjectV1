#!/usr/bin/env python3
"""
UDP Monitor: Listen on a range of UDP ports and print any received packets.

Usage:
  python3 src/optitrack/udp_monitor.py 9860 9900

Notes:
- Binds to 0.0.0.0 on each port in the inclusive range.
- Prints timestamp, port, sender address, and raw message.
- Gracefully exits on Ctrl+C.
"""

import socket
import threading
import sys
import time
from datetime import datetime


def listen_on_port(port: int, stop_event: threading.Event, host: str = "0.0.0.0") -> None:
    """Listen for UDP packets on a single port and print any received data."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.settimeout(0.5)
            print(f"[UDP-MON] ✓ Listening on {host}:{port}")

            while not stop_event.is_set():
                try:
                    data, addr = s.recvfrom(2048)
                    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    try:
                        msg = data.decode(errors='replace')
                    except Exception:
                        msg = str(data)
                    print(f"[{ts}] port={port} from={addr[0]}:{addr[1]} bytes={len(data)} | {msg}")
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[UDP-MON] ⚠️ port={port} error: {e}")
                    time.sleep(0.1)
    except OSError as e:
        print(f"[UDP-MON] ❌ Could not bind {host}:{port}: {e}")


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 src/optitrack/udp_monitor.py <start_port> <end_port>")
        return 1

    try:
        start_port = int(sys.argv[1])
        end_port = int(sys.argv[2])
    except ValueError:
        print("Ports must be integers.")
        return 1

    if start_port < 1 or end_port > 65535 or start_port > end_port:
        print("Invalid port range.")
        return 1

    print("\n=== UDP Monitor ===")
    print(f"Listening on ports {start_port}-{end_port} (inclusive) ...")
    print("Press Ctrl+C to stop.\n")

    stop_event = threading.Event()
    threads: list[threading.Thread] = []

    try:
        for port in range(start_port, end_port + 1):
            t = threading.Thread(target=listen_on_port, args=(port, stop_event), daemon=True)
            t.start()
            threads.append(t)

        # Keep main thread alive
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[UDP-MON] Stopping...")
    finally:
        stop_event.set()
        for t in threads:
            t.join(timeout=1.0)
        print("[UDP-MON] Done.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
