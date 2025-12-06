# UDP Broadcaster Documentation

## Overview

The UDP Broadcaster is a **push-based messaging system** that sends robot state data directly to pre-configured client IPs without requiring connection handshakes or heartbeats. This is in addition to the existing UDP Server that handles bi-directional communication with the local UI frontend.

## Key Differences: UDP Server vs UDP Broadcaster

| Feature | UDP Server | UDP Broadcaster |
|---------|------------|-----------------|
| **Connection model** | Pull-based: clients connect and send heartbeats | Push-based: sends to pre-configured IPs |
| **Client registration** | Clients register via `hello`/`ping` messages | No registration needed |
| **Message direction** | Bi-directional (commands + broadcasts) | Unidirectional (broadcasts only) |
| **Message format** | `robot_states` with all robots | `robot_state` per individual robot |
| **Target** | Local UI frontend | External embedded systems/displays |
| **Port strategy** | Single port (9998) for all data | Per-robot port for dedicated streams |
| **Failure handling** | Removes stale clients after TTL | Fire-and-forget (logs errors, continues) |

## Configuration

### Backend Config (`server/config.json`)

Add a `CLIENTS_CONFIG` section with the list of IPs to broadcast to:

```json
{
  "ROBOT_CONFIG": {
    "menelao": {
      "name": "menelao",
      "type": "real",
      "umh_id": "umh_4",
      "client_port": 9800,
      "cmd_vel_topic": "/menelao/cmd_vel"
    },
    "philip": {
      "name": "philip",
      "type": "real",
      "umh_id": "umh_5",
      "client_port": 9801,
      "cmd_vel_topic": "/philip/cmd_vel"
    }
  },
  "HYDRA_CONFIG": {
    "backend_host": "10.205.10.254",
    "backend_port": 9998,
    "state_broadcast_hz": 20
  },
  "CLIENTS_CONFIG": {
    "ips": ["10.205.3.4", "10.205.3.5", "192.168.1.100"]
  }
}
```

### Per-Robot Port Assignment

Each robot has a `client_port` field that determines which UDP port its state will be broadcast to on the configured client IPs.

- **`menelao`** → broadcasts to port `9800` on all client IPs
- **`philip`** → broadcasts to port `9801` on all client IPs
- **`dummy_1`** / **`dummy_2`** → set `client_port: 0` or `client_port: 1` to skip broadcasting

This allows clients to listen on specific ports for specific robots, enabling:
- Multiple single-board computers each dedicated to one robot
- Port-based filtering/routing in embedded systems
- Per-robot data streams without parsing full state bundles

## Message Format

### Individual Robot State (Broadcaster)

Unlike the UDP Server which sends `robot_states` with all robots, the broadcaster sends a `robot_state` message for **each robot individually**:

```json
{
  "type": "robot_state",
  "data": {
    "robot": "menelao",
    "x": 2.14,
    "y": -0.87,
    "yaw": -1.57,
    "type": "real",
    "is_following": true,
    "battery": {
      "voltage": 15.1,
      "percentage": 82.0,
      "current": -2.3,
      "temperature": 28.5,
      "charging": false,
      "power_supply_status": 2,
      "last_update": 1731094850.12
    },
    "imu": {
      "linear_accel": [0.02, -0.01, 9.81],
      "angular_velocity": [0.0, 0.0, 0.15],
      "orientation": [0.0, 0.0, -0.707, 0.707],
      "last_update": 1731094850.13
    },
    "path_following": {
      "distance_to_target": 0.42,
      "waypoint_index": 3,
      "total_waypoints": 7,
      "angle_to_target": 0.19,
      "current_offset": 0.0,
      "target_offset": 0.0,
      "time_on_waypoint": 1.2,
      "overshoot_count": 0
    }
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `robot` | string | Robot name/identifier |
| `x`, `y` | float | Position in meters (world coordinates) |
| `yaw` | float | Orientation in radians |
| `type` | string | `"real"` or `"dummy"` |
| `is_following` | bool | Whether robot is actively following a path |
| `battery` | object\|null | Battery telemetry (null if unavailable) |
| `imu` | object\|null | IMU telemetry (null if unavailable) |
| `path_following` | object\|null | Path follower state (only present if `is_following=true`) |

#### Battery Object

- `voltage` (float): Battery voltage in volts
- `percentage` (float): Battery level 0-100%
- `current` (float): Current draw in amperes (negative = discharging)
- `temperature` (float): Battery temperature in °C
- `charging` (bool): Whether battery is charging
- `power_supply_status` (int): ROS power supply status code
- `last_update` (float): Unix timestamp of last battery update

#### IMU Object

- `linear_accel` (tuple): Linear acceleration [x, y, z] in m/s²
- `angular_velocity` (tuple): Angular velocity [x, y, z] in rad/s
- `orientation` (tuple): Orientation quaternion [x, y, z, w]
- `last_update` (float): Unix timestamp of last IMU update

#### Path Following Object

- `distance_to_target` (float): Distance to current waypoint in meters
- `waypoint_index` (int): Current waypoint being tracked (0-indexed)
- `total_waypoints` (int): Total number of waypoints in path
- `angle_to_target` (float): Angular error to target in radians
- `current_offset` (float): Current lateral offset in meters
- `target_offset` (float): Target lateral offset in meters
- `time_on_waypoint` (float): Time spent pursuing current waypoint in seconds
- `overshoot_count` (int): Consecutive overshoot detections (diagnostic)

## Broadcast Frequency

The broadcaster uses the same frequency as the UDP Server, controlled by `HYDRA_CONFIG.state_broadcast_hz` (default: 20 Hz).

- **20 Hz** = 50 ms between updates (recommended for real-time control)
- **10 Hz** = 100 ms between updates (sufficient for monitoring)
- **50 Hz** = 20 ms between updates (high-frequency, may increase network load)

The broadcaster sends data **immediately** without buffering or client acknowledgment, maximizing throughput.

## Client Implementation Example

### Python UDP Receiver (Minimal)

```python
import socket
import json

# Listen for menelao's state on port 9800
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 9800))  # Listen on all interfaces

print("Listening for menelao state on port 9800...")

while True:
    data, addr = sock.recvfrom(65535)
    message = json.loads(data.decode('utf-8'))
    
    if message['type'] == 'robot_state':
        robot_data = message['data']
        print(f"Robot: {robot_data['robot']}")
        print(f"Position: ({robot_data['x']:.2f}, {robot_data['y']:.2f})")
        print(f"Yaw: {robot_data['yaw']:.2f} rad")
        
        if robot_data.get('battery'):
            bat = robot_data['battery']
            print(f"Battery: {bat['percentage']:.1f}% ({bat['voltage']:.2f}V)")
        
        if robot_data.get('path_following'):
            pf = robot_data['path_following']
            print(f"Path: waypoint {pf['waypoint_index']}/{pf['total_waypoints']}, "
                  f"dist={pf['distance_to_target']:.2f}m")
        print("---")
```

### C++ UDP Receiver (Embedded Systems)

```cpp
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <nlohmann/json.hpp>
#include <iostream>

using json = nlohmann::json;

int main() {
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    
    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(9800);  // menelao's port
    addr.sin_addr.s_addr = INADDR_ANY;
    
    bind(sock, (struct sockaddr*)&addr, sizeof(addr));
    
    char buffer[65536];
    while (true) {
        int len = recv(sock, buffer, sizeof(buffer), 0);
        buffer[len] = '\0';
        
        json msg = json::parse(buffer);
        
        if (msg["type"] == "robot_state") {
            auto data = msg["data"];
            std::cout << "Robot: " << data["robot"] << std::endl;
            std::cout << "Position: (" << data["x"] << ", " << data["y"] << ")" << std::endl;
            std::cout << "Yaw: " << data["yaw"] << " rad" << std::endl;
        }
    }
    
    return 0;
}
```

## Network Considerations

### Firewall Configuration

Ensure UDP traffic is allowed on the client ports:

```bash
# On client machine (example for Ubuntu/Debian)
sudo ufw allow 9800/udp  # menelao
sudo ufw allow 9801/udp  # philip
```

### Packet Loss

UDP does not guarantee delivery. For critical applications:

1. **Monitor update frequency:** Check that messages arrive at expected rate (e.g., 20 Hz)
2. **Timestamp validation:** Compare `last_update` timestamps to detect stale data
3. **Redundancy:** Use multiple client IPs if critical
4. **Fallback:** Implement timeout detection (e.g., no message for 500ms = connection lost)

### Network Load Estimation

Per robot, per client:
- Message size: ~300-500 bytes (depends on telemetry availability)
- Broadcast rate: 20 Hz
- **Bandwidth per robot**: ~10 KB/s = 80 Kbps

For 2 robots broadcasting to 3 clients:
- **Total bandwidth**: 2 × 3 × 80 Kbps = **480 Kbps** (negligible on modern networks)

## Troubleshooting

### No Messages Received on Client

1. **Check client IP in config:**
   ```bash
   # On backend server
   cat server/config.json | grep -A 5 CLIENTS_CONFIG
   ```

2. **Verify client port matches robot config:**
   ```bash
   # On backend server
   cat server/config.json | grep -A 3 "menelao"
   ```

3. **Test UDP connectivity:**
   ```bash
   # On client machine
   nc -ul 9800  # Listen on port 9800
   
   # Should see JSON messages if backend is running
   ```

4. **Check firewall:**
   ```bash
   # On client machine
   sudo iptables -L | grep 9800
   sudo ufw status | grep 9800
   ```

5. **Verify backend logs:**
   ```
   [UDPBroadcaster] Initialized with 1 client IPs: ['10.205.3.4']
   [UDPBroadcaster] Failed to send menelao state to ('10.205.3.4', 9800): [Errno 113] No route to host
   ```

### High Packet Loss

1. **Check network congestion:**
   ```bash
   ping -c 100 <client_ip>  # Check latency/loss
   ```

2. **Reduce broadcast frequency:**
   ```json
   "HYDRA_CONFIG": {
     "state_broadcast_hz": 10
   }
   ```

3. **Increase client socket buffer:**
   ```python
   sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2*1024*1024)  # 2MB buffer
   ```

### Messages Out of Order

UDP does not guarantee ordering. If message sequence matters:

1. **Use timestamps:** Include `time.time()` in your processing
2. **Buffer and sort:** Collect messages for 50-100ms, then process in order
3. **Ignore old messages:** Discard messages older than threshold

## Extending the Broadcaster

### Add Global Messages

To send non-robot-specific data (e.g., global status) to all clients on a common port:

```python
# In backend_server.py _broadcast_loop
if self.udp_broadcaster:
    global_status = {
        "type": "system_status",
        "data": {
            "ros_connected": True,
            "robot_count": len(robots_snapshot),
            "timestamp": time.time()
        }
    }
    self.udp_broadcaster.broadcast_to_all_clients(9999, global_status)
```

### Custom Message Types

Add new message types by modifying the broadcast loop:

```python
# Send IMU data separately for high-frequency processing
if robot.get_imu_state():
    imu_message = {
        "type": "imu_update",
        "data": {
            "robot": name,
            "imu": robot.get_imu_state()
        }
    }
    self.udp_broadcaster.send_robot_state(name, client_port + 100, imu_message)
```

### Multi-Network Broadcasting

To broadcast to multiple network interfaces:

```python
# In udp_broadcaster.py
self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
# Then broadcast to subnet broadcast address
self.client_ips.append("192.168.1.255")  # Broadcast to entire subnet
```

## Best Practices

1. **Port allocation:** Use sequential ports per robot (9800, 9801, 9802...) for easy management
2. **Dummy robots:** Set `client_port: 0` to exclude them from broadcasts
3. **Client validation:** Always check for `null` values in battery/IMU/path_following fields
4. **Timestamp monitoring:** Track `last_update` timestamps to detect stale data
5. **Error handling:** Handle JSON parsing errors gracefully (malformed packets)
6. **Performance:** The broadcaster is fire-and-forget; don't add acknowledgment logic
7. **Testing:** Use `nc -ul <port>` or Wireshark to verify broadcasts before deploying clients

## Related Documentation

- `udp_client.md` - Traditional UDP client implementation (bi-directional)
- `server.md` - Backend server architecture and control loops
- `core.md` - Robot state management and telemetry tracking

