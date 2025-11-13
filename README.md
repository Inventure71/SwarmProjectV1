# Hydra Robot Swarm Control System

Hydra is a modular control stack for coordinating real and simulated robots with OptiTrack-based motion capture, ROS command distribution, and an operator-focused desktop UI. The project is organized as a frontend application for interaction and a backend service that brokers state, telemetry, and motion commands.

## Repository Layout

- `local/` – Tk/ttk-based Hydra frontend, path planning tools, and operator services.
- `server/` – ROS-enabled backend that tracks robots, runs the path-following controller, and maintains UDP clients.
- `documentation/` – Detailed module-level references for control, tracking, services, and UI subsystems.
- `testing/` – Simulation helpers, diagnostics scripts, and ROS robot client utilities.
- `README.md` – This overview.

## Quick Start

### 1. Configure robots

Edit both `local/config.json` and `server/config.json` so the `ROBOT_CONFIG` entries match your fleet. Each robot entry supports:

- `name` – Unique identifier shown in the UI.
- `type` – `real` or `dummy`. Dummy robots run inside the backend for simulations.
- `umh_id` – OptiTrack rigid body identifier (used to infer ROS topics when unset).
- `cmd_vel_topic` – Override cmd_vel topic per robot when needed.
- `color` – Hex color used in the frontend (auto-generated if omitted).

Hydra connection parameters live under `HYDRA_CONFIG` (backend UDP host/port) and UI defaults under `CANVAS_CONFIG` (frontend only).

### 2. Start the backend (ROS environment)

```bash
cd /Users/inventure71/VSProjects/SwarmProjectV1/server
python3 backend_server.py
```

Requirements:
- ROS 1 with `rospy` available.
- OptiTrack ROS bridge publishing pose topics (see `documentation/optitrack.md`).
- Network reachability from the frontend host.

The backend opens a UDP server (default port `9998`), subscribes to tracked robot poses, applies the path follower, and streams state/battery/IMU telemetry back to clients.

### 3. Launch the Hydra frontend

```bash
cd /Users/inventure71/VSProjects/SwarmProjectV1/local
python3 frontend_app.py
```

Features include:
- Dashboard with live map, robot selection, and emergency stop.
- Path planning canvas (click or draw modes, JSON import/export).
- Monitoring tab for telemetry, follower status, and battery metrics.
- Recording service that captures driven trajectories through joystick control.

The UI auto-connects to the backend using the configured host/port and keeps parameters synced via the UDP client.

### 4. Run the robot client (ROS 2 execution environment)

```bash
cd /Users/inventure71/VSProjects/SwarmProjectV1/testing/robot_code
python3 move.py client <backend_ip> 6969
```

The client bridges UDP commands to ROS 2 `cmd_vel` (stamped or unstamped) and automatically reconnects if the TCP link drops.

### Optional: Simulate with dummy robots

Set `type: "dummy"` for any robot in `config.json`. The backend will simulate motion without hardware while still feeding the frontend UI.

## System Architecture

```
OptiTrack → ROS Tracker → Backend (UDP server + controllers)
                                   ↘
                              UDP broadcasts
                                   ↘
                 Hydra Frontend (UI, recording, path tools)
                                   ↘
                      Commands / parameters / telemetry
                                   ↘
                         Robots (ROS 2 cmd_vel via TCP)
```

- **Tracking:** `server/ros/ros_tracker.py` converts ROS pose topics into shared robot state.
- **Control loop:** `server/core/robot.py` and `server/control/path_follower.py` compute throttle/turn commands at 20 Hz with curvature-aware speed limiting.
- **Networking:** `server/net/udp_server.py` fans out state updates, acks, and error responses to every connected frontend client.
- **Frontend communications:** `local/frontend/udp_client.py` maintains a heartbeat, manages subscriptions, and caches robot/follower state for UI handlers.

## UDP Messaging Protocol

Hydra uses JSON payloads over UDP between the frontend (`UDPClient`) and backend (`UDPServer`). Every message has the schema:

```json
{
  "type": "<command-or-event>",
  "data": { ... context specific ... }
}
```

### Backend → Frontend broadcasts

- `robot_states` – Live pose & telemetry snapshot for each robot.
- `path_following_state` – Active follower diagnostics when a robot is tracking a path.
- `connection_status` – Aggregated ROS connectivity, registered robots, connected clients.
- `ack` – Command success confirmation (`data.command`, `data.status="ok"` plus optional payload).
- `error` – Command failure (`data.message` describing the issue).

Example broadcast bundle:

```json
{
  "type": "robot_states",
  "data": {
    "menelao": {
      "x": 2.14,
      "y": -0.87,
      "yaw": -1.57,
      "type": "real",
      "is_following": true,
      "battery": {
        "voltage": 15.1,
        "percentage": 82.0,
        "last_update": 1731094850.12
      },
      "imu": null
    }
  }
}
```

`path_following_state` reports the follower’s internal metrics, for example:

```json
{
  "type": "path_following_state",
  "data": {
    "menelao": {
      "distance_to_target": 0.42,
      "waypoint_index": 3,
      "total_waypoints": 7,
      "angle_to_target": 0.19,
      "current_offset": 0.0,
      "overshoot_count": 0
    }
  }
}
```

### Frontend → Backend commands

Most UI actions translate into the following command types (see `_cmd_*` handlers inside `server/backend_server.py`):

| Type | Purpose | Key fields |
| --- | --- | --- |
| `hello` / `ping` | Connection registration & heartbeat (sent automatically). | `timestamp` |
| `set_parameters` | Update control parameters for all robots. | Controller tuning keys |
| `set_path` | Upload waypoints for a robot. | `robot`, `waypoints` (list of `[x, y]`) |
| `clear_path` | Remove a robot’s active path. | `robot` |
| `start_path` / `stop_path` | Begin or halt path following for one robot. | `robot` |
| `start_all_paths` / `stop_all` | Bulk start/stop across all robots. | _none_ |
| `emergency_stop` | Immediate stop for every robot (aliases `stop_all`). | _none_ |
| `manual_control` | Direct throttle/turn command, cancels follower. | `robot`, `throttle`, `turn_rate` |
| `set_racing_config` | Adjust loop, offset, speed multiplier per robot. | `robot`, `offset`, `speed`, `loop` |
| `add_robot` / `remove_robot` | Modify robot roster and persist config. | `name`, optional `type`, `umh_id`, `cmd_vel_topic`, `max_linear`, `max_angular` |
| `get_diagnostics` | Request pose snapshot and ROS status info. | _none_ |

Sample command emitted by `CommandSender.push_path_to_backend`:

```json
{
  "type": "set_path",
  "data": {
    "robot": "menelao",
    "waypoints": [
      [0.0, 0.0],
      [1.2, 0.4],
      [2.4, 0.4]
    ]
  }
}
```

### Backend → ROS/Robots messaging

- Each real robot receives ROS `cmd_vel` commands via `ros/ros_controller.py` (Twist or TwistStamped).
- The ROS tracker consumes OptiTrack pose topics (`/natnet_ros/<umh_id>/pose`) and pushes updates into the backend state store.
- Dummy robots simulate motion internally and still produce state broadcasts to the frontend.

## Frontend Modules

- `ui/tabbed_interface.py`, `ui/tabs/` – Dashboard, robot management, monitoring, settings, and path planning views built on reusable ttk components.
- `ui/state/app_state.py` – Shared UI state (robots, zoom levels, mode flags) with thread-safe helpers.
- `ui/rendering/robot_renderer.py` & `ui/handlers/canvas_handler.py` – Canvas drawing, waypoint input, zoom/pan.
- `services/path_service.py` – Path CRUD, coordinate conversion, JSON persistence.
- `services/recording_service.py` – Record joystick-driven trajectories, sample intervals, and path previews.
- `frontend_app.py` – Composition root that wires configuration, services, handlers, and tabs into the Tk main loop.

Refer to `documentation/core.md`, `documentation/ui.md`, and `documentation/services.md` for deeper dives into these subsystems.

## Backend Modules

- `backend_server.py` – Entry point. Handles lifecycle, robot registration, command routing, and parameter syncing.
- `core/config_loader.py` – Shared loader that keeps JSON config on disk synchronized with runtime modifications.
- `core/robot.py` – Robot abstraction, path follower management, telemetry aggregation, dummy robot simulation.
- `control/path_follower.py` – Geometry-aware path controller with look-ahead blending, speed ramps, and loop support.
- `ros/ros_controller.py` – Sends cmd_vel commands using `rospy`, supports stamped or un-stamped publishers and per-robot limits.
- `trackers/` – Modular telemetry collectors (battery, IMU, odometry, velocity, range).
- `net/udp_server.py` – Connection tracking, state broadcasts, and request/response command handling.

Command handlers inside `backend_server.py` (prefixed `_cmd_`) expose robot management, path uploads, follower control, telemetry refresh, and configuration updates to the frontend.

## Testing, Simulation, and Utilities

- `testing/demo.py`, `testing/path_simulator.py` – Offline simulations for path follower behavior using recorded or synthetic data.
- `testing/test_udp_messages.py`, `testing/test_heartbeat.py` – Quick diagnostics for UDP connectivity and heartbeat logic.
- `testing/optitrack/udp_monitor.py` – Inspect OptiTrack UDP streams directly from the command line.
- `testing/server/` – Legacy server examples maintained for regression testing and comparison.

All scripts assume Python ≥3.10. Use a dedicated virtual environment per component to avoid ROS dependency conflicts (`rospy` for the backend, `rclpy` for the ROS 2 robot client, standard Python for the frontend).

## Extending Hydra

- **Add new robots:** Update `config.json` (frontend/backend) or call the backend `_cmd_add_robot` via UDP to persist configuration at runtime.
- **Custom trackers:** Implement a tracker under `server/trackers/` and register it in `backend_server.py` for streaming additional telemetry.
- **Alternate controllers:** Create a new strategy under `server/control/` and inject it through the robot factory (`server/core/robot.create_robot`) to support specialized drive systems.
- **UI customization:** Add new tabs in `ui/tabs/` or extend `TabbedInterface` for feature-specific workflows (e.g., calibration, analytics).

Follow the project’s design expectations: keep services cohesive, prefer dependency injection over hard-coded imports, and reuse core abstractions (`RobotStateProxy`, `RacingConfig`, `PathService`) to avoid duplication.

## Diagnostics & Troubleshooting

- **Frontend cannot connect:** Confirm backend UDP port in both configs, ensure no firewall dropping UDP 9998, and check the frontend console for `[UDPClient]` errors.
- **No robot motion:** Verify ROS topics (`rostopic echo /<robot>/cmd_vel`), ensure the robot is marked `real`, and confirm path follower is active via Monitoring tab.
- **Pose not updating:** Use `testing/optitrack/udp_monitor.py` to validate UDP packets and confirm `umh_id` matches the OptiTrack stream.
- **Telemetry stale:** Inspect backend logs for tracker registration messages; battery/IMU trackers require the robot to expose corresponding ROS topics.
- **UI lag:** Increase `state_broadcast_hz` or adjust canvas draw frequency by tuning `MonitoringTab` update intervals.

## Further Reading

- `documentation/core.md` – Core abstractions and configuration lifecycle.
- `documentation/services.md` – Path & recording services usage patterns.
- `documentation/server.md` – Backend command reference and control parameters.
- `documentation/ui.md` – UI architecture and theming.
- `documentation/control.md` – Path follower tuning and control theory background.

Contributions, bug reports, and design discussions are welcome. Please keep the codebase DRY, maintain service boundaries, and document new modules under `documentation/`.
