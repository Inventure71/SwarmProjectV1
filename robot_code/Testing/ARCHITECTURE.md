# Robot Control Architecture

## Overview

The robot control system uses a **dual-protocol architecture**:
1. **UDP** for receiving robot position data from OptiTrack
2. **TCP** for sending movement commands to robots

## Architecture Components

### 1. OptiTrack Tracking (UDP)
- **Protocol**: UDP (unidirectional: OptiTrack → Control System)
- **Implementation**: `RobotTracker` class in `src/optitrack/tracker.py`
- **Configuration**: Ports specified in `config.json` for each robot
- **Purpose**: Receive real-time position data (x, y, yaw) from OptiTrack system

**How it works:**
- Each robot has a dedicated UDP port (configured in `config.json`)
- OptiTrack broadcasts position data to these ports
- `RobotTracker` listens on these ports and updates robot positions
- Both `server_tracking_advanced.py` and `path_simulator_real.py` use this system

### 2. Robot Command Interface (TCP)
- **Protocol**: TCP (bidirectional but primarily Control System → Robot)
- **Architecture**: Server-Client pattern
- **Server**: Control system (`server_tracking_advanced.py` or `path_simulator_real.py`)
- **Client**: Robot running `move.py` in client mode

**How it works:**
- Control system starts a TCP server on port 6969
- Robot connects to the control system as a TCP client
- Control system sends JSON commands: `{"direction": 0/1, "angle": degrees_per_sec}`
- Robot executes commands via ROS 2 cmd_vel

## Connection Flow

```
┌─────────────────────┐
│   OptiTrack System  │
└──────────┬──────────┘
           │ UDP (position data)
           │ Port: 9880, 9881, etc.
           ▼
┌─────────────────────────────┐
│  Control System             │
│  - server_tracking_         │
│    advanced.py              │
│  - path_simulator_real.py   │
│                             │
│  Components:                │
│  • RobotTracker (UDP)       │
│  • TCP Server (port 6969)   │
└──────────┬──────────────────┘
           │ TCP (commands)
           │ Port: 6969
           ▼
┌─────────────────────┐
│  Robot              │
│  move.py client     │
│  → ROS 2 cmd_vel    │
└─────────────────────┘
```

## Usage

### Starting the Control System

#### Option 1: Advanced Tracking Server (Multi-robot with UI)
```bash
python3 src/server/server_tracking_advanced.py [port]
```
- Provides 2D map UI showing all robots
- Joystick control interface
- Broadcasts commands to all connected robots

#### Option 2: Path Simulator (Single robot with path planning)
```bash
python3 robot_code/Testing/path_simulator_real.py [robot_name]
```
- Focused on single robot control
- Draw paths on UI for robot to follow
- Includes delay compensation and prediction

### Starting the Robot

On the robot (Raspberry Pi):
```bash
python3 move.py client [server_host] [server_port]
```

Example:
```bash
python3 move.py client 10.205.3.47 6969
```

**Important**: The robot must be configured to connect to the control system's IP address!

## Key Differences from Previous Architecture

### Before (INCORRECT)
- `path_simulator_real.py` tried to connect TO the robot as a TCP client
- This is backwards! The robot expects to be a client, not a server

### After (CORRECT)
- `path_simulator_real.py` runs a TCP server (just like `server_tracking_advanced.py`)
- Robot connects to the control system as a TCP client
- This matches the architecture in `move.py` which runs `run_client_mode()`

## Configuration

Edit `config.json` to configure robots:

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

- `ip`: Robot's IP address (for reference, not used for OptiTrack tracking)
- `port`: UDP port for OptiTrack data

## Troubleshooting

### "Connection refused" error
- **Cause**: Robot is trying to connect to the control system, but the control system hasn't started its TCP server yet
- **Solution**: Start the control system FIRST, then start the robot

### No position updates from OptiTrack
- Check that OptiTrack is broadcasting to the correct UDP port
- Verify the port in `config.json` matches OptiTrack configuration
- Use `src/optitrack/udp_monitor.py` to test UDP reception

### Robot not responding to commands
- Verify TCP connection is established (check console messages)
- Check robot is running in client mode: `python3 move.py client [host] [port]`
- Ensure ROS 2 is running on the robot

## Code Structure

Both control systems follow the same pattern:

1. **Initialize OptiTrack tracking** (UDP)
   ```python
   self.tracker = RobotTracker(robot_config)
   self.tracker.start()
   ```

2. **Start TCP server**
   ```python
   self.controller = RobotController(host='0.0.0.0', port=6969)
   self.controller.start_server()
   ```

3. **Send commands**
   ```python
   self.controller.send_command(direction, angle)
   ```

This ensures consistent architecture across all control systems!

