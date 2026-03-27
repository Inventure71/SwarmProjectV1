# Scripts Guide

This folder contains deployment, runtime, and status utilities for the Mosaic ROS 2 swarm stack.

## Prerequisites

- Run commands from repo root unless noted.
- `ssh` key-based access to server/robot hosts is required (deploy runs non-interactively).
- For deploy scripts: `rsync`, `ssh`, and local Python 3 must be available.
- Remote machines must have ROS 2 installed, match configured `ros_setup` paths, and allow non-interactive privileged package install (`root` or passwordless `sudo`) for dependency bootstrap.

## `deploy_all.py`

What it does:
- Orchestrates deployment targets from `config/fleet.json` (`DEPLOYMENT_CONFIG`).
- Calls `deploy_server.sh`, `deploy_robot.sh`, and optionally `run_local_ui.sh`.

How to run:
```bash
python3 ./scripts/deploy_all.py
```

Common options:
```bash
python3 ./scripts/deploy_all.py --dry-run
python3 ./scripts/deploy_all.py --only server
python3 ./scripts/deploy_all.py --only server,robots --no-run
python3 ./scripts/deploy_all.py --only server,robots --autostart
python3 ./scripts/deploy_all.py --only robots --jobs 3
python3 ./scripts/deploy_all.py --only robots --jobs 3 --connect-timeout 3
```

Notes:
- Dependency installation is always performed during server/robot deploy (the `--use-rosdep` flag is now a deprecated no-op).
- `DEPLOYMENT_CONFIG.server.ros_setup` and `DEPLOYMENT_CONFIG.robots.defaults.ros_setup` are required; deploy/status scripts fail fast when missing.
- Manual startup script mode is default: deploy installs `mosaic_start.sh` per target and does not require boot-time autostart.
- Same manual start command works on server/robots: `bash <install_location>/mosaic_start.sh` (or `sudo bash <install_location>/mosaic_start.sh`).
- `--autostart` enables systemd-managed boot startup on targets.
- `--no-autostart` keeps manual startup-script mode (default).
- `--no-run` means deploy/build only for this invocation.
- `--jobs N` parallelizes robot deployments (`N>=1`). Default is `1` (sequential).
- `--connect-timeout N` bounds per-robot SSH precheck wait (`N>=1`) before parallel robot deploy starts.
- Robots that fail SSH precheck are skipped; a final summary reports succeeded/failed/skipped robots.

## `deploy_server.sh`

What it does:
- Syncs server/shared/orchestration ROS 2 packages + config to one server.
- Builds selected packages on remote.
- Installs a manual runtime launcher script at `<remote_root>/mosaic_start.sh`.
- In default mode, runtime is started by that script (manual trigger model).
- With `--autostart`, installs/updates `mosaic-supervisor.service` and can enable boot startup.
- Manual script runtime files:
  - `~/mosaic/logs/supervisor.log`
  - `~/mosaic/logs/supervisor.pid`

How to run:
```bash
bash ./scripts/deploy_server.sh --host <server-ip-or-host> --user <ssh-user> --ros-setup <remote-setup-path>
```

Example:
```bash
bash ./scripts/deploy_server.sh \
  --host 10.205.3.113 \
  --user hermes \
  --ros-setup /home/hermes/ros2_jazzy/install/setup.bash
```

Useful options:
- `--supervisor-ip <ip>` update `MOSAIC_CONFIG.supervisor_host` before sync
- `--use-rosdep` (deprecated no-op)
- `--no-clean`
- `--no-run`
- `--autostart`
- `--no-autostart`

## `deploy_robot.sh`

What it does:
- Syncs robot/shared/orchestration ROS 2 packages + config to one robot.
- Builds selected packages on remote.
- Installs a manual runtime launcher script at `<remote_root>/mosaic_start.sh`.
- In default mode, runtime is started by that script (manual trigger model).
- With `--autostart`, installs/updates `mosaic-robot-agent-<robot-name>.service` and can enable boot startup.
- Manual script runtime files:
  - `~/mosaic/logs/robot_<robot-name>.log`
  - `~/mosaic/logs/robot_<robot-name>.pid`

How to run:
```bash
bash ./scripts/deploy_robot.sh --host <robot-ip-or-host> --user <ssh-user> --robot-name <name> --ros-setup <remote-setup-path>
```

Example:
```bash
bash ./scripts/deploy_robot.sh \
  --host hypnos \
  --user husarion \
  --robot-name hypnos \
  --ros-setup /opt/ros/jazzy/setup.bash
```

Useful options:
- `--use-rosdep` (deprecated no-op)
- `--no-clean`
- `--no-run`
- `--autostart`
- `--no-autostart`

## `run_local_ui.sh`

What it does:
- Starts local Tk UI (`local/frontend_app.py`).
- Can run in foreground or background.

How to run:
```bash
bash ./scripts/run_local_ui.sh
bash ./scripts/run_local_ui.sh --python python3 --background
```

Background files:
- `local/ui.log`
- `local/ui.pid`

## `set_supervisor_ip.py`

What it does:
- Updates `MOSAIC_CONFIG.supervisor_host` in `config/fleet.json`.
- Validates IP format before writing.

How to run:
```bash
python3 ./scripts/set_supervisor_ip.py <ip>
```

Example:
```bash
python3 ./scripts/set_supervisor_ip.py 10.205.3.113
```

## `check_fleet_status.sh`

What it does:
- Reads enabled targets from `config/fleet.json`.
- Checks host reachability (`tcp/22`), SSH reachability, and remote process liveness via PID + process pattern.
- Optional `--check-ros` checks topic visibility from supervisor host.

How to run:
```bash
bash ./scripts/check_fleet_status.sh
bash ./scripts/check_fleet_status.sh --check-ros
```

Useful options:
- `--connect-timeout <seconds>`
- `--only server,robots`
- `--config <path>`

## Quick Workflow

1. Set/confirm deploy targets in `config/fleet.json`.
2. Deploy everything:
```bash
python3 ./scripts/deploy_all.py
```
3. Verify fleet runtime:
```bash
bash ./scripts/check_fleet_status.sh --check-ros
```
