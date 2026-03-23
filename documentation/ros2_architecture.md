# Hydra ROS 2 Architecture

## Overview

The repository is now ROS 2-only. The live system is the stack under `ros2_ws/`.

### Deployment-target layout

- `ros2_ws/src/server/`
  - `hydra_supervisor_bridge`
  - `hydra_optitrack_bridge`
- `ros2_ws/src/robots/`
  - `hydra_robot_agent`
- `ros2_ws/src/shared/`
  - `hydra_interfaces`
  - `hydra_common`
- `ros2_ws/src/orchestration/`
  - `hydra_bringup`

### Main components

- `hydra_robot_agent`
  Runs on each robot. Reads raw robot-local topics plus the configured OptiTrack pose topic, runs local autonomous path execution, and publishes normalized Hydra topics.
- `hydra_supervisor_bridge`
  Runs on the operator machine. Subscribes only to Hydra public topics and exports UDP to the Tk UI and Gama.
- `hydra_optitrack_bridge`
  Optional relay for pose topics when the external OptiTrack publisher topic names need remapping.
- `hydra_interfaces`
  Hydra public ROS 2 messages, services, and actions.
- `hydra_common`
  Shared controller/config logic used by agent and bridge.

## Public Topic Boundary

Raw ROSbot topics are private implementation details of the robot stack.

Public topics exposed by each robot:

- `/<robot>/hydra/status`
- `/<robot>/hydra/path_progress`
- `/<robot>/hydra/pose`
- `/<robot>/hydra/diagnostics`

The supervisor bridge should subscribe only to those Hydra topics.

## Shared Configuration

The shared config file is `config/fleet.json`.

It replaces the old duplicated frontend/backend config files as the source of truth for:

- fleet membership
- namespaces
- OptiTrack IDs
- topic overrides
- UI bridge endpoint
- Gama client ports/IPs

The existing loaders now prefer `config/fleet.json` automatically.

## Launching

### Supervisor bridge

```bash
cd ros2_ws
colcon build
source install/setup.bash
ros2 launch hydra_bringup supervisor.launch.py config_path:=/absolute/path/to/config/fleet.json
```

### Robot agent

```bash
cd ros2_ws
colcon build
source install/setup.bash
ros2 launch hydra_bringup robot_agent.launch.py robot_name:=menelao config_path:=/absolute/path/to/config/fleet.json
```

## UI / Gama Data Flow

- Tk UI speaks UDP only to `hydra_supervisor_bridge`
- Gama receives UDP only from `hydra_supervisor_bridge`
- No robot agent sends legacy UDP directly

## Current Limitations

- Runtime add/remove of robots is intentionally disabled
- Manual teleop remains a supervisor-to-`cmd_vel` exception for demos
- Autonomous path execution is robot-local only
- ROS 2 runtime validation still requires a real ROS 2 environment and message generation for `hydra_interfaces`
