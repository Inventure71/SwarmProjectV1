# Robot Swarm Control System

Modular robot control system with OptiTrack integration for path following and real-time tracking.

## Quick Start

### Path Drawing Application (Recommended)
```bash
python3 src/path_drawing_app.py [robot_name]
```
- Interactive UI to draw robot paths (click or pen mode)
- Real-time OptiTrack position tracking via UDP
- Automatic path following with look-ahead
- Distance-based speed control

**On the robot:**
```bash
python3 robot_code/move.py client <server_ip> 6969
```

### Multi-Robot Tracking Server
```bash
python3 src/server/server_tracking_advanced.py
```
- Map visualization of all robots
- Joystick control
- Broadcasts commands to all connected robots

### Barebones Server
```bash
python3 src/server/server_barebones.py
```
- Minimal terminal interface
- Direct command input

## Architecture

### Dual-Protocol System
- **UDP**: OptiTrack → Control System (position data)
- **TCP**: Control System → Robot (movement commands)

**Connection Flow:**
```
OptiTrack → UDP (port 9880+) → Control System
                                      ↓
                                TCP Server (port 6969)
                                      ↓
                                Robot Client (move.py)
                                      ↓
                                ROS 2 cmd_vel
```

### Modular Components

**`src/core/`**
- `config_loader.py` - Configuration management
- `robot.py` - Robot state and position tracking

**`src/optitrack/`**
- `tracker.py` - UDP listener for OptiTrack data
- `udp_monitor.py` - Debug tool for UDP ports

**`src/control/`**
- `path_follower.py` - Path following logic with prediction
- `robot_controller.py` - TCP server for robot communication

**`src/server/`**
- `server_tracking_advanced.py` - Multi-robot visualization
- `server_barebones.py` - Minimal control interface

## Configuration

Edit `config.json`:
```json
{
  "robots": {
    "umh_5": {
      "ip": "10.205.3.40",
      "port": 9880
    }
  }
}
```
- `ip`: Robot's IP address (for TCP connection)
- `port`: UDP port for OptiTrack data

## Path Drawing Features

### Two Drawing Modes

**Click Mode:**
- Click to add individual waypoints
- Shows numbered markers
- Precise point placement

**Draw Mode:**
- Click and drag to draw smooth paths
- Automatic point sampling
- Perfect for curves

### Motion Control

**Look-Ahead System:**
- Robot anticipates next waypoint
- Smooth transitions through path
- No stopping at intermediate points

**Smart Speed Control:**
- Full speed through intermediate waypoints
- Automatic slowdown at final waypoint only
- Distance-based deceleration

**Advanced Turning:**
- Up to 85°/s turn rate while moving
- Only stops for turns > 80°
- Smooth curved paths

## Robot Requirements

The robot must run `move.py` in client mode:
```bash
python3 move.py client <server_ip> 6969
```

**Command Format:**
```json
{
  "direction": 0/1,  // 0=turn in place, 1=move forward
  "angle": float     // degrees/second (positive=left, negative=right)
}
```

## Motion Parameters

Tuned for optimal performance:
- `waypoint_tolerance`: 0.20m (acceptable waypoint distance)
- `turn_in_place_threshold`: 80° (only turn in place if error > 80°)
- `max_turn_rate`: 85°/s (uses almost full robot capability)
- `proportional_gain`: 3.5 (turn rate aggressiveness)
- `look_ahead_distance`: 0.4m (start blending to next waypoint)
- `slow_down_distance`: 0.5m (decelerate near final waypoint)

## Debugging

**Check UDP Reception:**
```bash
python3 src/optitrack/udp_monitor.py <port>
```

**Verify Setup:**
1. OptiTrack broadcasts to correct UDP ports
2. Control system receives UDP packets (check terminal output)
3. Robot connects to TCP server
4. Position updates visible in UI

**Common Issues:**
- "Connection refused": Start control system before robot
- No position updates: Check OptiTrack port configuration
- Robot not responding: Verify TCP connection established

## Project Structure

```
SwarmProjectV1/
├── src/
│   ├── core/              # Configuration and robot state
│   ├── optitrack/         # OptiTrack UDP integration
│   ├── control/           # Path following and robot control
│   ├── server/            # Server applications
│   └── path_drawing_app.py  # Main path drawing application
├── robot_code/
│   ├── move.py            # Robot-side ROS 2 controller
│   └── Testing/           # Development and testing
├── config.json            # Robot configuration
└── README.md
```

## Usage Examples

### Single Robot Path Following
```bash
# Terminal 1: Start path drawing app
python3 src/path_drawing_app.py umh_5

# Terminal 2: On robot
python3 move.py client 10.205.3.47 6969
```

### Multi-Robot Monitoring
```bash
# Start tracking server
python3 src/server/server_tracking_advanced.py

# On each robot
python3 move.py client <server_ip> 6969
```

## Development

All components are modular and reusable:

```python
from src.control import PathFollower, RobotController
from src.optitrack.tracker import RobotTracker

# Setup tracking
tracker = RobotTracker(robot_config)
tracker.start()

# Setup control
controller = RobotController(port=6969)
controller.start_server()

# Create path follower
follower = PathFollower(
    waypoints=[(1.0, 0.0), (1.0, 1.0)],
    waypoint_tolerance=0.20,
    max_turn_rate=85.0
)

# Control loop
while not follower.is_complete():
    x, y, yaw = tracker.robots['umh_5'].get_position()
    follower.update_position(x, y, yaw)
    direction, turn_rate = follower.compute_command()
    controller.send_command(direction, turn_rate)
```
