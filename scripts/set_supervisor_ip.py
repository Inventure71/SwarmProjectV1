#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_config = repo_root / "config" / "fleet.json"

    parser = argparse.ArgumentParser(
        description="Set HYDRA_CONFIG.supervisor_host in config/fleet.json",
    )
    parser.add_argument("ip", help="Supervisor IP address (IPv4 or IPv6)")
    parser.add_argument(
        "--config",
        default=str(default_config),
        help="Path to fleet.json (default: %(default)s)",
    )
    return parser.parse_args()


def validate_ip(value: str) -> str:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid IP address: {value}") from exc
    return value


def main() -> None:
    args = parse_args()
    ip = validate_ip(args.ip)
    config_path = Path(args.config).expanduser().resolve()

    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    hydra_cfg = raw.setdefault("HYDRA_CONFIG", {})
    previous = hydra_cfg.get("supervisor_host")
    hydra_cfg["supervisor_host"] = ip

    config_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {config_path}")
    print(f"HYDRA_CONFIG.supervisor_host: {previous} -> {ip}")


if __name__ == "__main__":
    main()
