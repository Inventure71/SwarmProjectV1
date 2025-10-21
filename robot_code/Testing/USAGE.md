# Path Following System - Usage Guide

## Overview

This system provides modular path following capabilities for robots with OptiTrack tracking. All scripts use the `PathFollower` module for consistent, reusable control logic.

## Files

```
Testing/
├── path_follower.py           # Core module (import this)
├── demo.py                    # Simple demo (no UI)
├── path_simulator.py          # Virtual robot with UI
├── path_simulator_real.py     # Real robot with UI
├── DELAY_COMPENSATION.md      # Technical details
└── USAGE.md                   # This file
```

---

## Quick Start

### 1. Simple Demo (No UI)

Watch a simulated robot follow a square path in the terminal.

```bash
python3 demo.py
```

**Output:**
```
Path Following Demonstration
============================================================

Path: 4 waypoints
  1. (1.0m, 0.0m)
  2. (1.0m, 1.0m)
  3. (0.0m, 1.0m)
  4. (0.0m, 0.0m)

Starting path following...
[ 0.0s] Pos: ( 0.00,  0.00) | Heading:    0.0° | Target: 1/4 | Dist:  1.00m | [FORWARD]
...
```

### 2. Virtual Robot with UI

Interactive simulator - draw paths and watch virtual robot follow them.

```bash
python3 path_simulator.py
```

**Steps:**
1. Click on canvas to add waypoints
2. Click "▶ Start" to begin simulation
3. Watch blue robot follow your path
4. Use "⏸ Stop" / "🔄 Reset" / "🗑 Clear" as needed

### 3. Real Robot with UI

Control actual tracked robot.

```bash
# Step 1: Start the path simulator (runs TCP server on port 6969)
python3 path_simulator_real.py umh_5

# Step 2: On the robot (Raspberry Pi), connect to the server
python3 move.py client <server_ip> 6969
```

**Example:** If your laptop running path_simulator_real.py has IP `10.205.3.47`:
```bash
# On robot:
python3 move.py client 10.205.3.47 6969
```

**Steps:**
1. Click "🔌 Connect" - starts TCP server & OptiTrack tracking
2. Start robot in client mode (see above)
3. Wait for "✓ Server running - umh_5 connected" status
4. Click on canvas to draw path
5. Adjust delay slider if needed (typically 50-150ms)
6. Click "▶ Start" - robot follows path
7. Use "🛑 STOP" for emergency

**Architecture:**
- Control system runs a **TCP server** (port 6969)
- Robot connects as a **TCP client**
- OptiTrack data received via **UDP** (configured port per robot)

---

## Using PathFollower in Your Code

### Basic Integration

```python
from path_follower import PathFollower

# Define waypoints in meters
waypoints = [
    (1.0, 0.0),
    (1.0, 1.0),
    (0.0, 0.0)
]

# Create follower
follower = PathFollower(
    waypoints=waypoints,
    waypoint_tolerance=0.15,      # 15cm
    use_prediction=True,
    estimated_delay_ms=100
)

# Control loop
while not follower.is_complete():
    # Get robot position from YOUR tracking system
    x, y, yaw = get_robot_position()
    
    # Update follower
    follower.update_position(x, y, yaw)
    
    # Compute command
    direction, turn_rate = follower.compute_command()
    
    # Send to robot
    send_command_to_robot(direction, turn_rate)
    
    time.sleep(0.1)  # 10Hz

# Stop when done
send_command_to_robot(0, 0.0)
```

### With OptiTrack

```python
from src.core.config_loader import load_config
from src.optitrack.tracker import RobotTracker
from path_follower import PathFollower

# Setup tracking
config = load_config()
tracker_config = {'umh_5': config.get_robot_config()['umh_5']}
tracker = RobotTracker(tracker_config)
tracker.start()
robot = tracker.robots['umh_5']

# Create follower
waypoints = [(0.5, 0.0), (0.5, 0.5), (0.0, 0.0)]
follower = PathFollower(waypoints=waypoints)

# Control loop
while not follower.is_complete():
    x, y, yaw = robot.get_position()
    follower.update_position(x, y, yaw)
    direction, turn_rate = follower.compute_command()
    
    # Send to robot via your method
    send_tcp_command(direction, turn_rate)
    
    time.sleep(0.1)

tracker.stop()
```

### Dynamic Waypoints

```python
follower = PathFollower()  # Start empty

# Add waypoints during operation
follower.add_waypoint(1.0, 0.0)
follower.add_waypoint(1.0, 1.0)

while not follower.is_complete():
    # ... control loop ...
    
    # Add more waypoints on the fly
    if user_clicked():
        x, y = get_click_position()
        follower.add_waypoint(x, y)
```

---

## PathFollower API

### Constructor Parameters

```python
PathFollower(
    waypoints=[],                    # List of (x, y) tuples in meters
    waypoint_tolerance=0.15,         # Distance to consider reached (meters)
    turn_in_place_threshold=30.0,    # Angle to turn in place (degrees)
    proportional_gain=3.0,           # Turn rate control gain
    max_turn_rate=86.0,              # Max turn rate (deg/s)
    use_prediction=True,             # Enable position prediction
    estimated_delay_ms=100           # Tracking delay (milliseconds)
)
```

### Methods

| Method | Description |
|--------|-------------|
| `update_position(x, y, yaw)` | Update current robot position |
| `compute_command()` | Get next command: `(direction, turn_rate)` |
| `is_complete()` | Check if path is done |
| `get_progress()` | Returns `(current_waypoint, total_waypoints)` |
| `get_state()` | Get detailed state dict for monitoring |
| `set_waypoints(waypoints)` | Replace waypoints and reset |
| `add_waypoint(x, y)` | Add single waypoint |
| `clear_waypoints()` | Remove all waypoints |
| `reset()` | Reset to start of path |

### Command Format

`compute_command()` returns `(direction, turn_rate)`:
- **direction**: `0` = turn in place, `1` = move forward
- **turn_rate**: degrees/second (positive = left, negative = right)

Send to robot as:
```json
{"direction": 0/1, "angle": turn_rate}
```

---

## Configuration

### Tuning Parameters

**Waypoint Tolerance** (`waypoint_tolerance`):
- How close to get before moving to next waypoint
- Too small: robot may never "reach" waypoint due to noise
- Too large: imprecise path following
- **Recommended**: 0.10 - 0.20 meters

**Turn-in-Place Threshold** (`turn_in_place_threshold`):
- Angle error that triggers turning in place before moving
- Too small: robot tries to move while badly aligned
- Too large: excessive turning, slow progress
- **Recommended**: 25 - 35 degrees

**Proportional Gain** (`proportional_gain`):
- Multiplier for turn rate based on angle error
- Higher = more aggressive turning
- Lower = gentler turns
- **Recommended**: 2.0 - 4.0

**Estimated Delay** (`estimated_delay_ms`):
- OptiTrack tracking delay
- WiFi: ~50-150ms
- Wired: ~30-80ms
- Measure with: ping time + processing time
- **Recommended**: 80 - 120 ms for WiFi

### Delay Compensation

**Enable prediction** for systems with tracking delay:
```python
follower = PathFollower(
    use_prediction=True,
    estimated_delay_ms=100
)
```

**Disable prediction** if:
- Your position source is real-time (encoders, no network delay)
- Delay is < 20ms
- You have your own compensation

See `DELAY_COMPENSATION.md` for technical details.

---

## Robot Requirements

The system expects robots to:
1. Accept commands via TCP as JSON: `{"direction": 0/1, "angle": deg/s}`
2. Have max speed ~0.5 m/s
3. Have max turn rate ~1.5 rad/s (86 deg/s)
4. Position tracked in meters, heading in radians

Adjust `PathFollower` parameters if your robot has different limits.

---

## Troubleshooting

**Robot overshoots waypoints:**
- Increase `waypoint_tolerance`
- Decrease `proportional_gain`
- Increase `estimated_delay_ms`

**Robot turns too much:**
- Decrease `proportional_gain`
- Increase `turn_in_place_threshold`

**Robot zigzags:**
- Increase `estimated_delay_ms` (delay compensation needed)
- Enable `use_prediction=True`
- Decrease control loop frequency

**Robot doesn't move:**
- Check TCP connection
- Verify robot is running `move.py client`
- Check OptiTrack is broadcasting

**Path never completes:**
- Check waypoint tolerance isn't too small
- Verify position updates are happening
- Check for obstacles preventing movement

---

## Examples

### Square Pattern
```python
waypoints = [
    (1.0, 0.0), (1.0, 1.0),
    (0.0, 1.0), (0.0, 0.0)
]
```

### Circle Approximation
```python
import math
waypoints = [
    (math.cos(a), math.sin(a))
    for a in [i * math.pi/4 for i in range(8)]
]
```

### Figure-8
```python
waypoints = [
    (0.5, 0.0), (0.5, 0.5), (0.0, 0.5), (-0.5, 0.5),
    (-0.5, 0.0), (-0.5, -0.5), (0.0, -0.5), (0.5, -0.5),
    (0.5, 0.0)
]
```

---

## Advanced Usage

### Monitor Progress
```python
while not follower.is_complete():
    x, y, yaw = get_position()
    follower.update_position(x, y, yaw)
    
    state = follower.get_state()
    print(f"Waypoint {state['waypoint_index']+1}/{state['total_waypoints']}")
    print(f"Distance: {state['distance_to_target']:.2f}m")
    print(f"Angle: {math.degrees(state['angle_to_target']):.1f}°")
    
    direction, turn_rate = follower.compute_command()
    send_command(direction, turn_rate)
```

### Pause and Resume
```python
waypoints_backup = follower.waypoints.copy()
current_index = follower.current_waypoint_index

# ... robot stops ...

# Resume later
follower.set_waypoints(waypoints_backup)
follower.current_waypoint_index = current_index
```

### Multiple Robots
```python
followers = {}
for robot_name in ['umh_2', 'umh_3', 'umh_5']:
    followers[robot_name] = PathFollower(waypoints=get_waypoints(robot_name))

while any(not f.is_complete() for f in followers.values()):
    for name, follower in followers.items():
        if follower.is_complete():
            continue
        
        x, y, yaw = get_robot_position(name)
        follower.update_position(x, y, yaw)
        direction, turn_rate = follower.compute_command()
        send_command(name, direction, turn_rate)
```

