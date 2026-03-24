# Hydra ROS 2 Swarm Demo

Hydra is now a ROS 2-first robot demo stack built around deployment-target slices:

- `ros2_ws/` – the live system
  - `src/robots/hydra_robot_agent`: robot-local autonomy and normalized Hydra topics
  - `src/server/hydra_supervisor_bridge`: ROS 2 to UDP bridge for the Tk UI and Gama
  - `src/server/hydra_optitrack_bridge`: optional pose-topic relay
  - `src/shared/hydra_interfaces`: public ROS 2 interfaces
  - `src/shared/hydra_common`: shared controller/config logic
  - `src/orchestration/hydra_bringup`: launch orchestration package
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

Raw ROSbot topics are private implementation details. Each robot runs `hydra_robot_agent`, which reads robot-local topics and the configured OptiTrack pose topic, runs local path following, and publishes normalized Hydra topics:

- `/<robot>/hydra/status`
- `/<robot>/hydra/path_progress`
- `/<robot>/hydra/pose`
- `/<robot>/hydra/diagnostics`

`hydra_supervisor_bridge` subscribes only to those Hydra topics. It then:

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
- `pose_flip_x` to mirror OptiTrack X into Hydra world frame (defaults to natnet_ros topics)
- `client_port` for Gama UDP
- visual color

Global config:

- `HYDRA_CONFIG.supervisor_host` / `supervisor_port`
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
- It also updates `HYDRA_CONFIG.supervisor_host` automatically from `DEPLOYMENT_CONFIG.server.host` when the host is an IP.
- Remote launch commands run in background and write logs under `~/hydra/logs/`.
- Use `--only server` / `--only robots` / `--only ui` to scope deployment.
- Use `--dry-run` to print commands without executing them.
- Use `--jobs N` (for robot target) to deploy multiple robots in parallel.
- Use `--connect-timeout N` to bound SSH precheck wait per robot when running parallel robot deploy.
- Robots that fail SSH precheck are skipped, and deploy prints an end-of-run summary of succeeded/failed/skipped robots.
- Deploy scripts now always run dependency bootstrap (`rosdep` + workspace dependency install) on targets before build.
- Targets must allow non-interactive privileged package install (`root` or passwordless `sudo`) and have working apt repositories.
- Deploy uses non-interactive SSH; set up key-based auth to each target host.

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
ros2 launch hydra_bringup robot_agent.launch.py \
  robot_name:=menelao \
  config_path:=/Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/config/fleet.json
```

### 3. Start the supervisor bridge

```bash
ros2 launch hydra_bringup supervisor.launch.py \
  config_path:=/Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/config/fleet.json
```

### 4. Start the UI

```bash
cd local
python3 frontend_app.py
```

The UI connects by UDP to the supervisor bridge, not to a centralized ROS controller.

## Runtime Expectations

- If a robot is healthy and receiving OptiTrack pose, it publishes Hydra topics.
- The supervisor bridge aggregates those topics and mirrors them to the UI and Gama.
- Starting a path from the UI submits a ROS 2 `follow_path` action to the robot agent.
- The robot follows the path locally.
- Stopping the supervisor while a robot is active should trigger the robot’s safe-stop behavior.

## Status

The legacy centralized backend has been removed from the intended runtime path. The remaining repo should be treated as ROS 2-only.

See [documentation/ros2_architecture.md](/Users/inventure71/VSProjects/RoboticsLabProjects/SwarmProjectV1/documentation/ros2_architecture.md) for more detail.
