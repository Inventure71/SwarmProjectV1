# Scripts Guide

This folder contains deployment, runtime, and status utilities for the Hydra ROS 2 swarm stack.

## Prerequisites

- Run commands from repo root unless noted.
- `ssh` key-based access to server/robot hosts is recommended.
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
```

Notes:
- Dependency installation is always performed during server/robot deploy (the `--use-rosdep` flag is now a deprecated no-op).

## `deploy_server.sh`

What it does:
- Syncs server/shared/orchestration ROS 2 packages + config to one server.
- Builds selected packages on remote.
- Optionally launches supervisor bridge in background and writes:
  - `~/hydra/logs/supervisor.log`
  - `~/hydra/logs/supervisor.pid`

How to run:
```bash
bash ./scripts/deploy_server.sh --host <server-ip-or-host> --user <ssh-user>
```

Example:
```bash
bash ./scripts/deploy_server.sh \
  --host 10.205.3.113 \
  --user hermes \
  --ros-setup /home/hermes/ros2_jazzy/install/setup.bash
```

Useful options:
- `--supervisor-ip <ip>` update `HYDRA_CONFIG.supervisor_host` before sync
- `--use-rosdep` (deprecated no-op)
- `--no-clean`
- `--no-run`

## `deploy_robot.sh`

What it does:
- Syncs robot/shared/orchestration ROS 2 packages + config to one robot.
- Builds selected packages on remote.
- Optionally launches robot agent in background and writes:
  - `~/hydra/logs/robot_<robot-name>.log`
  - `~/hydra/logs/robot_<robot-name>.pid`

How to run:
```bash
bash ./scripts/deploy_robot.sh --host <robot-ip-or-host> --user <ssh-user> --robot-name <name>
```

Example:
```bash
bash ./scripts/deploy_robot.sh \
  --host hypnos \
  --user husarion \
  --robot-name hypnos
```

Useful options:
- `--use-rosdep` (deprecated no-op)
- `--no-clean`
- `--no-run`

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
- Updates `HYDRA_CONFIG.supervisor_host` in `config/fleet.json`.
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
