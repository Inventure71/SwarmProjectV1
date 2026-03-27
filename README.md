# Mosaic ROS 2 Swarm Demo

Mosaic is now a ROS 2-first robot demo stack built around deployment-target slices:

- `ros2_ws/` – the live system
  - `src/robots/mosaic_robot_agent`: robot-local autonomy and normalized Mosaic topics
  - `src/server/mosaic_supervisor_bridge`: ROS 2 to UDP bridge for the Tk UI and Gama
  - `src/server/mosaic_optitrack_bridge`: optional pose-topic relay
  - `src/shared/mosaic_interfaces`: public ROS 2 interfaces
  - `src/shared/mosaic_common`: shared controller/config logic
  - `src/orchestration/mosaic_bringup`: launch orchestration package
- `local/` – the Tk demo UI, still speaking UDP to the supervisor bridge
- `config/fleet.json` – shared fleet and endpoint configuration

## Repository Layout By Device Role

- `ros2_ws/src/server/`
  Install/deploy these packages on the supervisor machine.
- `ros2_ws/src/robots/`
  Install/deploy these packages on robot computers.
- `ros2_ws/src/shared/`
  Shared contracts and logic required by both sides.
- `ros2_ws/src/orchestration/`
  Launch files used to run agents/bridge.
- `local/`
  Operator UI (can run on supervisor or a separate operator laptop).

## Architecture

Raw ROSbot topics are private implementation details. Each robot runs `mosaic_robot_agent`, which reads robot-local topics and the configured OptiTrack pose topic, runs local path following, and publishes normalized Mosaic topics:

- `/<robot>/mosaic/status`
- `/<robot>/mosaic/path_progress`
- `/<robot>/mosaic/pose`
- `/<robot>/mosaic/diagnostics`

`mosaic_supervisor_bridge` subscribes only to those Mosaic topics. It then:

- serves UDP to the Tk UI
- exports UDP to Gama
- forwards high-level commands into ROS 2

Autonomous path execution is robot-local. Direct supervisor writes to `cmd_vel` are only used for manual teleop.

## Configuration

Edit [config/fleet.json](/Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/config/fleet.json).

Per robot:

- `name`
- `ip` (used by deployment automation for SSH target host)
- `namespace`
- `type`
- `umh_id`
- `cmd_vel_topic`
- telemetry topic overrides when needed
- `pose_flip_x` to mirror OptiTrack X into Mosaic world frame (defaults to natnet_ros topics)
- `client_port` for Gama UDP
- visual color

Global config:

- `MOSAIC_CONFIG.supervisor_host` / `supervisor_port`
  These are the UDP endpoint for the supervisor bridge that the UI connects to.
- Quick update helper:
  `./scripts/set_supervisor_ip.py 10.205.3.113`
- `CLIENTS_CONFIG.ips`
  Target IPs for Gama UDP export.
- `CANVAS_CONFIG`
  UI canvas defaults.
- `DEPLOYMENT_CONFIG`
  SSH/runtime metadata used by `scripts/deploy_all.py` (server and robot host/user/ROS setup paths, plus optional UI run flags).
  Robot host can be specified either in `DEPLOYMENT_CONFIG.robots.devices.<robot>.host` or directly in `ROBOT_CONFIG.<robot>.ip`.

## Setup

### Quick Deploy Scripts (Recommended)

Configure device SSH/runtime settings in `config/fleet.json` under `DEPLOYMENT_CONFIG`, then run one command:

```bash
python3 ./scripts/deploy_all.py
```

Examples (full commands):

- Most inclusive command (deploy server + all enabled robots + local UI, then launch services):
```bash
python3 ./scripts/deploy_all.py \
  --repo-root /Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1 \
  --config /Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/config/fleet.json \
  --only server,robots,ui
```

- Deploy only server + robots (no local UI):
```bash
python3 ./scripts/deploy_all.py \
  --repo-root /Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1 \
  --config /Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/config/fleet.json \
  --only server,robots
```

- Build/sync only (no launch):
```bash
python3 ./scripts/deploy_all.py \
  --repo-root /Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1 \
  --config /Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/config/fleet.json \
  --only server,robots,ui \
  --no-run
```

- Enable systemd autostart mode (optional):
```bash
python3 ./scripts/deploy_all.py --only server,robots --autostart
```

- Dry-run preview (print commands without executing):
```bash
python3 ./scripts/deploy_all.py \
  --repo-root /Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1 \
  --config /Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/config/fleet.json \
  --only server,robots,ui \
  --dry-run
```

- Parallel robot deploy (faster for many robots):
```bash
python3 ./scripts/deploy_all.py --only robots --jobs 3
```

- Parallel robot deploy with a short SSH precheck timeout (useful when some robots are offline):
```bash
python3 ./scripts/deploy_all.py --only robots --jobs 3 --connect-timeout 3
```

- Scope to one target:
```bash
python3 ./scripts/deploy_all.py --only server
python3 ./scripts/deploy_all.py --only robots
python3 ./scripts/deploy_all.py --only ui
```

Notes:
- `deploy_all.py` orchestrates:
  - server deployment (`scripts/deploy_server.sh`)
  - each enabled robot deployment (`scripts/deploy_robot.sh`)
  - optional local UI startup (`scripts/run_local_ui.sh`)
- It also updates `MOSAIC_CONFIG.supervisor_host` automatically from `DEPLOYMENT_CONFIG.server.host` when the host is an IP.
- Default runtime mode is **manual startup script**:
  - deploy installs `mosaic_start.sh` on each target at `<remote_root>/mosaic_start.sh`
  - same command on server and robots: `bash <install_location>/mosaic_start.sh` (or `sudo bash <install_location>/mosaic_start.sh`)
- `--no-run` keeps deploy/build behavior but does not start runtime now.
- `--autostart` enables systemd-managed boot startup instead:
  - server: `mosaic-supervisor.service`
  - robot: `mosaic-robot-agent-<robot-name>.service`
- `--no-autostart` keeps/forces manual startup script mode.
- Use `--only server` / `--only robots` / `--only ui` to scope deployment.
- Use `--dry-run` to print commands without executing them.
- Use `--jobs N` (for robot target) to deploy multiple robots in parallel.
- Use `--connect-timeout N` to bound SSH precheck wait per robot when running parallel robot deploy.
- Robots that fail SSH precheck are skipped, and deploy prints an end-of-run summary of succeeded/failed/skipped robots.
- Deploy scripts now always run dependency bootstrap (`rosdep` + workspace dependency install) on targets before build.
- Targets must allow non-interactive privileged package install (`root` or passwordless `sudo`) and have working apt repositories.
- Deploy uses non-interactive SSH; set up key-based auth to each target host.
- Service troubleshooting (only when using `--autostart`):
  - `ssh <user>@<host> 'sudo systemctl status mosaic-supervisor.service'`
  - `ssh <user>@<host> 'sudo journalctl -u mosaic-supervisor.service -n 100 --no-pager'`
  - `ssh <user>@<host> 'sudo systemctl status mosaic-robot-agent-<robot-name>.service'`
  - `ssh <user>@<host> 'sudo journalctl -u mosaic-robot-agent-<robot-name>.service -n 100 --no-pager'`

### Fleet Status Check

Use the status helper to verify from your local machine that hosts are reachable and remote launch processes are still alive:

```bash
./scripts/check_fleet_status.sh
```

Optional ROS validation (run `ros2 topic echo --once` checks from the supervisor host):

```bash
./scripts/check_fleet_status.sh --check-ros
```

Notes:
- The script reads enabled targets from `config/fleet.json` (`DEPLOYMENT_CONFIG.server` and `DEPLOYMENT_CONFIG.robots.devices`).
- SSH checks are non-interactive (`BatchMode=yes`), so key-based auth is expected.

### 1. Build the ROS 2 workspace

```bash
cd ros2_ws
colcon build
source install/setup.bash
```

### 2. Start one robot agent per robot

```bash
ros2 launch mosaic_bringup robot_agent.launch.py \
  robot_name:=menelao \
  config_path:=/Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/config/fleet.json
```

### 3. Start the supervisor bridge

```bash
ros2 launch mosaic_bringup supervisor.launch.py \
  config_path:=/Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/config/fleet.json
```

### 4. Start the UI

```bash
cd local
python3 frontend_app.py
```

The UI connects by UDP to the supervisor bridge, not to a centralized ROS controller.

## Runtime Expectations

- If a robot is healthy and receiving OptiTrack pose, it publishes Mosaic topics.
- The supervisor bridge aggregates those topics and mirrors them to the UI and Gama.
- Starting a path from the UI submits a ROS 2 `follow_path` action to the robot agent.
- The robot follows the path locally.
- Stopping the supervisor while a robot is active should trigger the robot’s safe-stop behavior.

## Status

The legacy centralized backend has been removed from the intended runtime path. The remaining repo should be treated as ROS 2-only.

See [documentation/ros2_architecture.md](/Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/documentation/ros2_architecture.md) for more detail.
