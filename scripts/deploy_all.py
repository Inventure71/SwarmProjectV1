#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        description="Deploy Mosaic to all devices configured in config/fleet.json",
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
    autostart_group = parser.add_mutually_exclusive_group()
    autostart_group.add_argument(
        "--autostart",
        action="store_true",
        help="Enable systemd autostart management on targets (disabled by default)",
    )
    autostart_group.add_argument(
        "--no-autostart",
        action="store_true",
        help="Deprecated alias; autostart is already disabled by default",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Parallel robot deployment jobs (default: %(default)s)",
    )
    parser.add_argument(
        "--connect-timeout",
        type=int,
        default=3,
        help="SSH connect timeout in seconds for robot precheck (default: %(default)s)",
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


def require_non_empty(value: Any, field_path: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise SystemExit(f"Missing required {field_path} in fleet config")
    return text


def is_valid_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def precheck_robot_ssh_access(
    targets: list[tuple[str, str, str]],
    connect_timeout: int,
) -> tuple[set[str], dict[str, str]]:
    """
    Probe robot SSH access and classify targets as reachable/unreachable.

    Also accepts unknown host keys non-interactively (`accept-new`) so parallel runs
    do not block on first-connect prompts.
    """
    reachable: set[str] = set()
    failures: dict[str, str] = {}
    if not targets:
        return reachable, failures
    print(f"[deploy_all] running SSH precheck for enabled robots (timeout={connect_timeout}s)...")
    for robot_name, host, user in targets:
        target = f"{user}@{host}"
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=" + str(connect_timeout),
                    "-o",
                    "ConnectionAttempts=1",
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    target,
                    "true",
                ],
                check=False,
                text=True,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=connect_timeout + 2,
            )
        except subprocess.TimeoutExpired:
            failures[robot_name] = f"timed out after {connect_timeout + 2}s"
            continue
        if result.returncode == 0:
            reachable.add(robot_name)
            continue
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        failures[robot_name] = detail

    return reachable, failures


def deploy_server(
    repo_root: Path,
    deployment_cfg: dict[str, Any],
    no_run: bool,
    autostart: bool,
    dry_run: bool,
) -> None:
    server = deployment_cfg.get("server", {})
    if not as_bool(server.get("enabled"), False):
        print("[deploy_all] server deployment disabled, skipping.")
        return

    host = str(server.get("host", "")).strip()
    user = str(server.get("user", "")).strip()
    ros_setup = require_non_empty(server.get("ros_setup"), "DEPLOYMENT_CONFIG.server.ros_setup")
    remote_root = str(server.get("remote_root", f"/home/{user}/mosaic")).strip()
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
    if autostart:
        cmd.append("--autostart")

    run(cmd, repo_root, dry_run)


def deploy_robots(
    repo_root: Path,
    config: dict[str, Any],
    deployment_cfg: dict[str, Any],
    no_run: bool,
    autostart: bool,
    dry_run: bool,
    jobs: int,
    connect_timeout: int,
) -> None:
    robots_cfg = deployment_cfg.get("robots", {})
    defaults = robots_cfg.get("defaults", {})
    devices = robots_cfg.get("devices", {})
    robot_map = config.get("ROBOT_CONFIG", {})

    if not isinstance(devices, dict) or not devices:
        print("[deploy_all] no robots.devices entries found; skipping robot deployment.")
        return

    deploy_commands: list[tuple[str, str, str, list[str]]] = []
    for robot_name, device_cfg in devices.items():
        if not as_bool(device_cfg.get("enabled"), False):
            continue
        if robot_name not in robot_map:
            raise SystemExit(f"DEPLOYMENT_CONFIG.robots.devices contains unknown robot '{robot_name}'")
        robot_cfg = robot_map[robot_name]

        host = str(device_cfg.get("host", robot_cfg.get("ip", ""))).strip()
        user = str(device_cfg.get("user", defaults.get("user", ""))).strip()
        device_ros_setup = device_cfg.get("ros_setup")
        if device_ros_setup is None:
            ros_setup = require_non_empty(
                defaults.get("ros_setup"),
                "DEPLOYMENT_CONFIG.robots.defaults.ros_setup",
            )
        else:
            ros_setup = require_non_empty(
                device_ros_setup,
                f"DEPLOYMENT_CONFIG.robots.devices.{robot_name}.ros_setup",
            )
        remote_root = str(device_cfg.get("remote_root", defaults.get("remote_root", f"/home/{user}/mosaic"))).strip()
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
        if autostart:
            cmd.append("--autostart")

        deploy_commands.append((robot_name, host, user, cmd))

    if not deploy_commands:
        print("[deploy_all] no enabled robots found in robots.devices; skipping robot deployment.")
        return

    if dry_run:
        for _, _, _, cmd in deploy_commands:
            run(cmd, repo_root, dry_run)
        return

    reachable_robots, precheck_failures = precheck_robot_ssh_access(
        [(robot_name, host, user) for robot_name, host, user, _ in deploy_commands],
        connect_timeout=connect_timeout,
    )
    if precheck_failures:
        print("[deploy_all] skipping robots that failed SSH precheck:")
        for robot_name in sorted(precheck_failures):
            print(f"[deploy_all]   - {robot_name}: {precheck_failures[robot_name]}")

    runnable_commands = [
        (robot_name, host, user, cmd)
        for robot_name, host, user, cmd in deploy_commands
        if robot_name in reachable_robots
    ]
    if not runnable_commands:
        skipped_sorted = sorted(precheck_failures)
        skipped_details = ", ".join(f"{name} ({precheck_failures[name]})" for name in skipped_sorted)
        print("[deploy_all] robot deployment summary:")
        print("[deploy_all]   succeeded (0): -")
        print("[deploy_all]   failed (0): -")
        print(f"[deploy_all]   skipped ({len(skipped_sorted)}): {skipped_details if skipped_details else '-'}")
        print("[deploy_all] robot deployment skipped: no reachable robots.")
        raise SystemExit(1)

    max_workers = min(jobs, len(runnable_commands))
    if max_workers > 1:
        print(f"[deploy_all] deploying {len(runnable_commands)} reachable robots in parallel (jobs={max_workers})")
    else:
        print(f"[deploy_all] deploying {len(runnable_commands)} reachable robot(s) sequentially")

    for _, _, _, cmd in runnable_commands:
        print("+", shlex.join(cmd))

    succeeded: list[str] = []
    failures: list[str] = []

    if max_workers <= 1:
        for robot_name, _, _, cmd in runnable_commands:
            result = subprocess.run(
                cmd,
                cwd=str(repo_root),
                check=False,
                text=True,
                capture_output=True,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                succeeded.append(robot_name)
                print(f"[deploy_all] [{robot_name}] OK")
                if result.stdout.strip():
                    print(f"[deploy_all] [{robot_name}] output:\n{result.stdout.rstrip()}")
                continue

            failures.append(robot_name)
            print(f"[deploy_all] [{robot_name}] FAILED (exit {result.returncode})")
            if result.stdout.strip():
                print(f"[deploy_all] [{robot_name}] stdout:\n{result.stdout.rstrip()}")
            if result.stderr.strip():
                print(f"[deploy_all] [{robot_name}] stderr:\n{result.stderr.rstrip()}", file=sys.stderr)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    subprocess.run,
                    cmd,
                    cwd=str(repo_root),
                    check=False,
                    text=True,
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                ): (robot_name, cmd)
                for robot_name, _, _, cmd in runnable_commands
            }
            for future in as_completed(futures):
                robot_name, _ = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # pragma: no cover - defensive runtime guard
                    failures.append(robot_name)
                    print(f"[deploy_all] [{robot_name}] failed to launch deploy process: {exc}")
                    continue

                if result.returncode == 0:
                    succeeded.append(robot_name)
                    print(f"[deploy_all] [{robot_name}] OK")
                    if result.stdout.strip():
                        print(f"[deploy_all] [{robot_name}] output:\n{result.stdout.rstrip()}")
                    continue

                failures.append(robot_name)
                print(f"[deploy_all] [{robot_name}] FAILED (exit {result.returncode})")
                if result.stdout.strip():
                    print(f"[deploy_all] [{robot_name}] stdout:\n{result.stdout.rstrip()}")
                if result.stderr.strip():
                    print(f"[deploy_all] [{robot_name}] stderr:\n{result.stderr.rstrip()}", file=sys.stderr)

    succeeded_sorted = sorted(succeeded)
    failed_sorted = sorted(failures)
    skipped_sorted = sorted(precheck_failures)
    print("[deploy_all] robot deployment summary:")
    print(f"[deploy_all]   succeeded ({len(succeeded_sorted)}): {', '.join(succeeded_sorted) if succeeded_sorted else '-'}")
    print(f"[deploy_all]   failed ({len(failed_sorted)}): {', '.join(failed_sorted) if failed_sorted else '-'}")
    if skipped_sorted:
        skipped_details = ", ".join(f"{name} ({precheck_failures[name]})" for name in skipped_sorted)
        print(f"[deploy_all]   skipped ({len(skipped_sorted)}): {skipped_details}")
    else:
        print("[deploy_all]   skipped (0): -")

    if failures or precheck_failures:
        print("[deploy_all] robot deployment completed with failures/skips. See summary above.")
        raise SystemExit(1)


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
    if args.jobs < 1:
        raise SystemExit("--jobs must be >= 1")
    if args.connect_timeout < 1:
        raise SystemExit("--connect-timeout must be >= 1")
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
    if args.autostart:
        print("[deploy_all] autostart mode: enabled (systemd services installed/managed).")
    else:
        print("[deploy_all] startup mode: manual (mosaic_start.sh installed; no boot autostart).")

    if "server" in targets:
        deploy_server(
            repo_root=repo_root,
            deployment_cfg=deployment,
            no_run=args.no_run,
            autostart=args.autostart,
            dry_run=args.dry_run,
        )

    if "robots" in targets:
        deploy_robots(
            repo_root=repo_root,
            config=cfg,
            deployment_cfg=deployment,
            no_run=args.no_run,
            autostart=args.autostart,
            dry_run=args.dry_run,
            jobs=args.jobs,
            connect_timeout=args.connect_timeout,
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
