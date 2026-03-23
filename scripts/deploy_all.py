#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Deploy Hydra to all devices configured in config/fleet.json",
    )
    parser.add_argument(
        "--repo-root",
        default=str(repo_root),
        help="Repository root (default: %(default)s)",
    )
    parser.add_argument(
        "--config",
        default=str(repo_root / "config" / "fleet.json"),
        help="Path to fleet config (default: %(default)s)",
    )
    parser.add_argument(
        "--only",
        default="server,robots",
        help="Comma-separated targets: server,robots,ui (default: %(default)s)",
    )
    parser.add_argument(
        "--use-rosdep",
        action="store_true",
        help="Deprecated no-op (dependencies are always installed by deploy scripts)",
    )
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="Sync/build only; do not launch services",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them",
    )
    return parser.parse_args()


def run(cmd: list[str], cwd: Path, dry_run: bool) -> None:
    print("+", shlex.join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, cwd=str(cwd), check=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def is_valid_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def deploy_server(
    repo_root: Path,
    deployment_cfg: dict[str, Any],
    no_run: bool,
    dry_run: bool,
) -> None:
    server = deployment_cfg.get("server", {})
    if not as_bool(server.get("enabled"), False):
        print("[deploy_all] server deployment disabled, skipping.")
        return

    host = str(server.get("host", "")).strip()
    user = str(server.get("user", "")).strip()
    ros_setup = str(server.get("ros_setup", "/opt/ros/jazzy/setup.bash")).strip()
    remote_root = str(server.get("remote_root", f"/home/{user}/hydra")).strip()
    run_after = as_bool(server.get("run_after_deploy"), True)

    if not host or not user:
        raise SystemExit("DEPLOYMENT_CONFIG.server.host and .user are required when server.enabled=true")

    cmd = [
        "bash",
        str(repo_root / "scripts" / "deploy_server.sh"),
        "--host",
        host,
        "--user",
        user,
        "--ros-setup",
        ros_setup,
        "--remote-root",
        remote_root,
    ]

    if is_valid_ip(host):
        cmd += ["--supervisor-ip", host]
    else:
        print(f"[deploy_all] warning: server host '{host}' is not a literal IP; skipping --supervisor-ip update.")

    if no_run or not run_after:
        cmd.append("--no-run")

    run(cmd, repo_root, dry_run)


def deploy_robots(
    repo_root: Path,
    config: dict[str, Any],
    deployment_cfg: dict[str, Any],
    no_run: bool,
    dry_run: bool,
) -> None:
    robots_cfg = deployment_cfg.get("robots", {})
    defaults = robots_cfg.get("defaults", {})
    devices = robots_cfg.get("devices", {})
    robot_map = config.get("ROBOT_CONFIG", {})

    if not isinstance(devices, dict) or not devices:
        print("[deploy_all] no robots.devices entries found; skipping robot deployment.")
        return

    for robot_name, device_cfg in devices.items():
        if not as_bool(device_cfg.get("enabled"), False):
            continue
        if robot_name not in robot_map:
            raise SystemExit(f"DEPLOYMENT_CONFIG.robots.devices contains unknown robot '{robot_name}'")
        robot_cfg = robot_map[robot_name]

        host = str(device_cfg.get("host", robot_cfg.get("ip", ""))).strip()
        user = str(device_cfg.get("user", defaults.get("user", ""))).strip()
        ros_setup = str(device_cfg.get("ros_setup", defaults.get("ros_setup", "/opt/ros/jazzy/setup.bash"))).strip()
        remote_root = str(device_cfg.get("remote_root", defaults.get("remote_root", f"/home/{user}/hydra"))).strip()
        run_after = as_bool(device_cfg.get("run_after_deploy"), as_bool(defaults.get("run_after_deploy"), True))

        if not host or host.startswith("REPLACE_WITH_"):
            raise SystemExit(
                f"Robot '{robot_name}' has invalid/missing host. Set ROBOT_CONFIG.{robot_name}.ip or DEPLOYMENT_CONFIG.robots.devices.{robot_name}.host"
            )
        if not user:
            raise SystemExit(f"Robot '{robot_name}' requires deployment user (defaults.user or device user)")

        cmd = [
            "bash",
            str(repo_root / "scripts" / "deploy_robot.sh"),
            "--host",
            host,
            "--user",
            user,
            "--robot-name",
            robot_name,
            "--ros-setup",
            ros_setup,
            "--remote-root",
            remote_root,
        ]
        if no_run or not run_after:
            cmd.append("--no-run")

        run(cmd, repo_root, dry_run)


def deploy_ui(repo_root: Path, deployment_cfg: dict[str, Any], dry_run: bool) -> None:
    ui = deployment_cfg.get("ui", {})
    if not as_bool(ui.get("enabled"), False):
        print("[deploy_all] ui deployment disabled, skipping.")
        return

    mode = str(ui.get("mode", "local")).strip().lower()
    if mode != "local":
        raise SystemExit("Only DEPLOYMENT_CONFIG.ui.mode='local' is currently supported")

    python_bin = str(ui.get("python", "python3")).strip()
    background = as_bool(ui.get("background"), False)

    cmd = [
        "bash",
        str(repo_root / "scripts" / "run_local_ui.sh"),
        "--python",
        python_bin,
    ]
    if background:
        cmd.append("--background")

    run(cmd, repo_root, dry_run)


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    targets = {t.strip().lower() for t in args.only.split(",") if t.strip()}
    valid_targets = {"server", "robots", "ui"}
    unknown = sorted(targets - valid_targets)
    if unknown:
        raise SystemExit(f"Unknown --only targets: {', '.join(unknown)}")

    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    cfg = load_json(config_path)
    deployment = cfg.get("DEPLOYMENT_CONFIG")
    if not isinstance(deployment, dict):
        raise SystemExit("Missing DEPLOYMENT_CONFIG in fleet config")

    if args.use_rosdep:
        print("[deploy_all] --use-rosdep is deprecated; dependency installation is now always enabled.")

    if "server" in targets:
        deploy_server(
            repo_root=repo_root,
            deployment_cfg=deployment,
            no_run=args.no_run,
            dry_run=args.dry_run,
        )

    if "robots" in targets:
        deploy_robots(
            repo_root=repo_root,
            config=cfg,
            deployment_cfg=deployment,
            no_run=args.no_run,
            dry_run=args.dry_run,
        )

    if "ui" in targets:
        deploy_ui(
            repo_root=repo_root,
            deployment_cfg=deployment,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
