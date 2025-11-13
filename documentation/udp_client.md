## Hydra UDP Client Integration

This guide documents how any external client can talk to the Hydra backend over UDP and reliably receive the same telemetry as the bundled frontend.

### Connection Prerequisites

- Bind a UDP socket on the client side (any local port is fine; binding to port `0` lets the OS choose).
- Send packets to the backend host/port configured under `HYDRA_CONFIG.backend_host` and `HYDRA_CONFIG.backend_port` (default `9998`).
- Encode every packet as UTF-8 JSON with the canonical structure:

```json
{
  "type": "<command-or-event>",
  "data": { /* command specific payload */ }
}
```

### Registration and Heartbeat

1. **Hello** – Immediately after opening the socket, send:
   ```json
   {
     "type": "hello",
     "data": { "timestamp": 1731094800.123 }
   }
   ```
   This registers the client with the backend’s UDP server.

2. **Ping** – Keep the session alive by sending:
   ```json
   {
     "type": "ping",
     "data": { "timestamp": 1731094860.456 }
   }
   ```
   Repeat more frequently than the backend’s `client_ttl` (30 s by default; the stock frontend pings every 10 s).

Failure to maintain the heartbeat will cause the backend to drop the client, stopping broadcast messages.

### Broadcast Messages Received

Once registered, the backend continuously sends the following message types to every connected client:

| Type | Description |
| --- | --- |
| `robot_states` | Pose, robot type, follower status, and optional battery/IMU metrics for each registered robot. |
| `path_following_state` | Debug data for robots actively following a path: waypoint index, distance to target, target offsets, and overshoot counts. |
| `connection_status` | Overall ROS connectivity, list of tracked/controlled robots, and number of connected UDP clients. |
| `ack` | Acknowledgement for any command you send. Includes `data.command`, `data.status` and may echo extra details. |
| `error` | Indicates a rejected command. Contains `data.message` explaining the failure. |

#### Sample `robot_states`

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
        "current": null,
        "last_update": 1731094850.12
      },
      "imu": null
    }
  }
}
```

#### Sample `path_following_state`

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
      "target_offset": 0.0,
      "overshoot_count": 0,
      "time_on_waypoint": 0.75
    }
  }
}
```

### Commands You Can Send

UI actions map to UDP commands processed by `_cmd_*` handlers in `server/backend_server.py`. A non-exhaustive list:

| Command | Purpose | Essential Fields |
| --- | --- | --- |
| `set_parameters` | Update path follower tuning globally. | Controller parameter keys such as `look_ahead_distance`, `proportional_gain`, etc. |
| `set_path` | Upload waypoints for a robot. | `robot`, `waypoints` (list of `[x, y]`). |
| `clear_path` | Remove stored waypoints. | `robot`. |
| `start_path` / `stop_path` | Start or stop following a path. | `robot`. |
| `start_all_paths` / `stop_all` | Bulk start/stop across all robots. | None. |
| `emergency_stop` | Immediate global stop (alias of `stop_all`). | None. |
| `manual_control` | Direct throttle/turn control (cancels follower). | `robot`, `throttle`, `turn_rate`. |
| `set_racing_config` | Adjust loop mode, offset, speed multiplier. | `robot`, optional `offset`, `speed`, `loop`. |
| `add_robot` / `remove_robot` | Modify robot roster and persist config. | `name`, optional metadata (`type`, `umh_id`, `cmd_vel_topic`, `max_linear`, `max_angular`). |
| `get_diagnostics` | Request current tracked poses and ROS status (response arrives as an `ack`). | None. |

Example command:

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

The backend will reply:

```json
{
  "type": "ack",
  "data": {
    "command": "set_path",
    "status": "ok",
    "num_waypoints": 3
  }
}
```

If the command fails, you will instead receive:

```json
{
  "type": "error",
  "data": {
    "message": "Robot 'menelao' not registered"
  }
}
```

### Reliability Considerations

- **Stateless packets:** Treat each broadcast as a full snapshot—cache the latest payloads locally if you need persistent state.
- **Ordering:** UDP does not guarantee order. Overwrite cached data rather than applying diffs.
- **Loss:** Periodic broadcasts mean dropped packets self-heal, but commands should wait for an `ack` to confirm success.
- **Timeouts:** If `connection_status` has not been received for several cycles, send a `ping` and verify that the backend still acknowledges commands.

### Summary Checklist

1. Open UDP socket to Hydra backend host/port.
2. Send `hello` followed by periodic `ping`.
3. Deserialize and process broadcasts (`robot_states`, `path_following_state`, `connection_status`, `ack`, `error`).
4. Issue commands using documented JSON shapes and wait for `ack`/`error`.
5. Cache last-known state client-side and handle packet loss/order issues gracefully.

Following these steps ensures a custom client can control robots, observe telemetry, and stay in sync with the Hydra backend alongside the default frontend.

