# Robot Swarm Control System

OptiTrack-integrated robot control system with two server options.

## Quick Start

### Barebones (Terminal)
```bash
python3 src/server/server_tracking_barebones.py
```
- Terminal interface
- Type commands: `1 0` (forward), `p` (positions), `s` (stop), `q` (quit)

### Advanced (GUI)
```bash
python3 src/server/server_tracking_advanced.py
```
- Map visualization
- Joystick control
- Position text display

### Path Planning (GUI)
```bash
python3 src/server/server_path_planning.py
```
- Click canvas to draw waypoints
- Robot automatically follows path
- Real-time position tracking

## Features

- **OptiTrack Integration**: Real-time position tracking via UDP
- **TCP Command Server**: Broadcast commands to robots
- **Multiple Robots**: Configure via `config.json`
- **Debug Output**: See UDP packet reception in terminal

## Configuration

Edit `config.json`:
```json
{
  "ROBOT_CONFIG": {
    "umh_2": {"ip": "192.168.1.2", "port": 9876},
    "umh_3": {"ip": "192.168.1.3", "port": 9877}
  }
}
```

## Debugging

Check `DEBUG_GUIDE.md` for:
- How to verify UDP reception
- What debug messages to look for
- Troubleshooting steps

## Files

- `src/server/server_tracking_advanced.py` - GUI with joystick
- `src/server/server_tracking_barebones.py` - Terminal interface
- `src/server/server_path_planning.py` - Path drawing & following
- `src/core/robot.py` - Robot class with position tracking
- `src/optitrack/tracker.py` - UDP listener for OptiTrack
- `src/optitrack/udp_monitor.py` - Debug tool for UDP ports
- `config.json` - Robot configuration

