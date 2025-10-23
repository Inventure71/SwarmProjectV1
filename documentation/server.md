# Server Module Documentation

## Overview
The server module provides TCP server implementations for robot control. It includes both basic command-line servers and advanced GUI servers with real-time tracking and control capabilities.

## Components

### 1. BarebonesServer Class (`server_barebones.py`)

Simple command-line server for basic robot control and command broadcasting.

#### Key Features
- **Command-line Interface**: Interactive command input
- **TCP Server**: Listens for robot connections
- **Command Broadcasting**: Sends commands to all connected robots
- **Legacy Support**: Maintains compatibility with older robot protocols

#### Parameters

##### Server Configuration
- **`host`**: Server host address (default: '0.0.0.0')
  - **Impact**: Controls which network interfaces to bind to
  - **Tuning**: Use '0.0.0.0' for all interfaces, specific IP for single interface
  - **Range**: Valid IP addresses

- **`port`**: Server port (default: 6969)
  - **Impact**: Must match robot client configuration
  - **Tuning**: Use different ports for multiple servers
  - **Range**: 1024-65535 (avoid system ports)

##### Command Parameters
- **`throttle`**: Forward/backward command ratio (-1.0 to 1.0)
  - **Impact**: Controls linear velocity
  - **Tuning**: 
    - 0.0 = stop
    - 0.1-0.3 = slow movement
    - 0.4-0.7 = medium speed
    - 0.8-1.0 = full speed
    - Negative values = reverse

- **`angle`**: Turn rate in degrees/second
  - **Impact**: Controls angular velocity
  - **Tuning**:
    - 0 = straight
    - 10-30 = gentle turns
    - 30-60 = medium turns
    - 60-90 = sharp turns
    - Negative = opposite direction

#### Methods
- **`run()`**: Start server and command loop
- **`broadcast_command(throttle, angle)`**: Send command to all clients
- **`handle_client(client_socket, address)`**: Handle client connection

#### Usage Example
```python
from server.server_barebones import BarebonesServer

# Create server
server = BarebonesServer(host='0.0.0.0', port=6969)

# Run server
server.run()
```

#### Command Examples
```
Command: 1 0      # Move forward straight
Command: 0.6 60  # Move forward at 60% with 60°/s turn
Command: -0.5 0  # Move backward at 50%
Command: 0 90    # Stop linear, turn in place 90°/s
Command: 0 0     # Full stop
Command: quit    # Exit server
```

### 2. AdvancedTrackingServer Class (`server_tracking_advanced.py`)

Advanced server with GUI, real-time tracking, and joystick control.

#### Key Features
- **Real-time Tracking**: Displays robot positions from OptiTrack
- **GUI Interface**: Modern graphical user interface
- **Joystick Control**: Virtual joystick for robot control
- **Speed Control**: Adjustable speed slider
- **Multi-robot Support**: Handles multiple robots simultaneously

#### Parameters

##### Server Configuration
- **`host`**: Server host address (default: '0.0.0.0')
- **`port`**: Server port (default: 6969)

##### Control Parameters
- **`max_speed`**: Maximum linear speed (default: 0.5 m/s)
  - **Impact**: Limits maximum robot speed
  - **Tuning**: Adjust based on robot capabilities
  - **Range**: 0.1 - 2.0 m/s

- **`max_angle`**: Maximum turn rate (default: 85°/s)
  - **Impact**: Limits maximum angular velocity
  - **Tuning**: Adjust based on robot capabilities
  - **Range**: 10° - 180°/s

##### Map Parameters
- **`map_min_x`, `map_max_x`**: X-axis bounds (default: -10.0 to 10.0m)
- **`map_min_y`, `map_max_y`**: Y-axis bounds (default: -10.0 to 10.0m)
  - **Impact**: Controls map display area
  - **Tuning**: Adjust based on workspace size
  - **Range**: -50.0 to 50.0m

##### Robot Visualization Parameters
- **`robot_colors`**: Colors for different robots
  - **Impact**: Visual distinction between robots
  - **Tuning**: Use contrasting colors
  - **Values**: Hex color codes

- **`update_interval`**: UI update frequency (default: 100ms)
  - **Impact**: Controls refresh rate
  - **Tuning**: Lower values = smoother updates
  - **Range**: 50-500ms

#### Methods
- **`run()`**: Start server and GUI
- **`_update_ui()`**: Update UI elements
- **`_emergency_stop()`**: Emergency stop function
- **`shutdown()`**: Shutdown server

#### Usage Example
```python
from server.server_tracking_advanced import AdvancedTrackingServer

# Create advanced server
server = AdvancedTrackingServer(host='0.0.0.0', port=6969)

# Run server
server.run()
```

## Movement Control Parameters

### Speed Control Tuning

#### For Precise Movement
```python
# Conservative speed settings
max_speed = 0.3  # m/s
max_angle = 60.0  # deg/s
```

#### For Fast Movement
```python
# Aggressive speed settings
max_speed = 0.8  # m/s
max_angle = 120.0  # deg/s
```

#### For Obstacle-Rich Environments
```python
# Safe speed settings
max_speed = 0.4  # m/s
max_angle = 45.0  # deg/s
```

### Joystick Control Parameters

#### Sensitivity Tuning
```python
# High sensitivity
joystick_sensitivity = 1.0

# Medium sensitivity
joystick_sensitivity = 0.7

# Low sensitivity
joystick_sensitivity = 0.5
```

#### Control Mapping
```python
# Map joystick to robot commands
throttle = joystick_y * speed_slider_value
turn_rate = -joystick_x * max_angle
```

## Common Issues and Solutions

### Server Connection Issues

#### 1. Server Not Starting
**Symptoms**: Server fails to start
**Solutions**:
- Check port availability
- Verify host configuration
- Check firewall settings
- Test with different ports

#### 2. Robots Not Connecting
**Symptoms**: No robot connections
**Solutions**:
- Check network connectivity
- Verify robot client configuration
- Check port forwarding
- Test with barebones server

#### 3. Commands Not Reaching Robots
**Symptoms**: Robots not responding to commands
**Solutions**:
- Check command format
- Verify robot client code
- Test with simple commands
- Check network latency

### GUI Issues

#### 1. UI Not Updating
**Symptoms**: Static display, no position updates
**Solutions**:
- Check OptiTrack connection
- Verify tracking configuration
- Check update interval
- Test with manual updates

#### 2. Joystick Not Working
**Symptoms**: No response to joystick input
**Solutions**:
- Check event bindings
- Verify joystick widget
- Test with different inputs
- Check control mapping

#### 3. Map Display Issues
**Symptoms**: Robots not visible on map
**Solutions**:
- Check coordinate transformation
- Verify map bounds
- Check robot position data
- Test with known positions

### Performance Issues

#### 1. Slow Updates
**Symptoms**: Laggy interface
**Solutions**:
- Increase update interval
- Optimize drawing operations
- Check system performance
- Reduce update frequency

#### 2. High CPU Usage
**Symptoms**: High CPU consumption
**Solutions**:
- Optimize update loops
- Reduce drawing operations
- Check for infinite loops
- Profile application

#### 3. Memory Issues
**Symptoms**: High memory usage
**Solutions**:
- Clear old drawings
- Limit canvas objects
- Check for memory leaks
- Optimize data structures

## Advanced Configuration

### Custom Map Bounds
```python
# Large workspace
server.map_min_x = -20.0
server.map_max_x = 20.0
server.map_min_y = -20.0
server.map_max_y = 20.0

# Small workspace
server.map_min_x = -5.0
server.map_max_x = 5.0
server.map_min_y = -5.0
server.map_max_y = 5.0
```

### Custom Robot Colors
```python
# Custom color scheme
server.robot_colors = [
    '#FF6B6B',  # Red
    '#4ECDC4',  # Teal
    '#45B7D1',  # Blue
    '#FFA07A',  # Orange
    '#98D8C8',  # Green
    '#F7DC6F'   # Yellow
]
```

### Performance Optimization
```python
# High performance settings
server.update_interval = 50  # 20 FPS
server.max_speed = 0.5
server.max_angle = 85.0

# Low performance settings
server.update_interval = 200  # 5 FPS
server.max_speed = 0.3
server.max_angle = 60.0
```

## Integration with Other Modules

### With OptiTrack Module
- Receives position updates
- Displays robot positions
- Handles coordinate transformations
- Manages tracking threads

### With Control Module
- Sends movement commands
- Processes joystick input
- Manages robot connections
- Handles command broadcasting

### With UI Module
- Uses UI components
- Handles user interactions
- Manages visual feedback
- Processes control input

## Best Practices

### 1. Server Configuration
- Use appropriate ports
- Configure network settings
- Test with multiple robots
- Monitor connection status

### 2. GUI Design
- Use consistent styling
- Provide clear feedback
- Handle errors gracefully
- Test with different screen sizes

### 3. Performance
- Monitor update frequency
- Optimize drawing operations
- Check resource usage
- Test with multiple robots

### 4. Safety
- Implement emergency stop
- Monitor robot status
- Handle connection failures
- Provide user feedback

## Troubleshooting Checklist

### Server Issues
1. Check port availability
2. Verify network configuration
3. Test with different ports
4. Check firewall settings
5. Monitor connection status

### GUI Issues
1. Check OptiTrack connection
2. Verify tracking configuration
3. Test with manual updates
4. Check event bindings
5. Verify control mapping

### Performance Issues
1. Monitor update frequency
2. Check system resources
3. Optimize drawing operations
4. Test with different settings
5. Profile application

### Robot Issues
1. Check robot connections
2. Verify command format
3. Test with simple commands
4. Check network latency
5. Monitor robot response

## Usage Examples

### Basic Server Setup
```python
# Start barebones server
python3 src/server/server_barebones.py

# Start advanced server
python3 src/server/server_tracking_advanced.py
```

### Custom Port
```python
# Use custom port
python3 src/server/server_barebones.py 8080
python3 src/server/server_tracking_advanced.py 8080
```

### Robot Connection
```python
# Robot client connection
import socket
import json

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('server_ip', 6969))

# Send command
command = {"throttle": 0.5, "angle": 30.0}
sock.sendall(json.dumps(command).encode('utf-8'))
```

### Emergency Stop
```python
# Emergency stop command
command = {"throttle": 0.0, "angle": 0.0}
sock.sendall(json.dumps(command).encode('utf-8'))
```
