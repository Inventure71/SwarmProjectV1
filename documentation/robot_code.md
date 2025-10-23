# Robot Code Module Documentation

## Overview
The robot_code module provides the robot-side implementation for receiving and executing movement commands. It includes ROS 2 integration, TCP client functionality, and movement control algorithms.

## Components

### 1. RobotController Class (`move.py`)

ROS 2-based robot controller that receives commands from the server and publishes movement commands to the robot.

#### Key Features
- **ROS 2 Integration**: Publishes Twist messages to robot
- **TCP Client**: Connects to control server
- **Movement Control**: Converts commands to robot movements
- **Automatic Reconnection**: Handles connection failures gracefully

#### Critical Parameters for Robot Movement

##### Speed Limits
- **`max_linear`**: Maximum linear speed (default: 0.5 m/s)
  - **Impact**: Limits maximum forward/backward speed
  - **Tuning**: 
    - Lower values (0.2-0.4 m/s) = safer, more controlled movement
    - Higher values (0.6-1.0 m/s) = faster movement, less precise
    - **Range**: 0.1 - 2.0 m/s

- **`max_angular`**: Maximum angular speed (default: 1.5 rad/s)
  - **Impact**: Limits maximum turn rate
  - **Tuning**:
    - Lower values (0.5-1.0 rad/s) = smoother turns
    - Higher values (1.5-3.0 rad/s) = faster turns, potentially jerky
    - **Range**: 0.1 - 5.0 rad/s

##### Control Parameters
- **`use_stamped`**: Use TwistStamped messages (default: True)
  - **Impact**: Adds timestamp to messages
  - **Tuning**: Keep enabled for better ROS 2 compatibility
  - **Values**: True/False

- **`frame_id`**: Reference frame ID (default: 'base_link')
  - **Impact**: Specifies robot's coordinate frame
  - **Tuning**: Should match robot's actual frame
  - **Values**: 'base_link', 'odom', 'map', etc.

##### Rate Control
- **`rate_hz`**: Control loop frequency (default: 20.0 Hz)
  - **Impact**: How often commands are published
  - **Tuning**:
    - Lower values (10-15 Hz) = less responsive, smoother
    - Higher values (20-30 Hz) = more responsive, potentially jerky
    - **Range**: 5 - 50 Hz

#### Methods
- **`set_movement(throttle, angle)`**: Set robot movement
- **`stop()`**: Stop robot movement
- **`_on_timer()`**: Timer callback for publishing
- **`_publish_immediate()`**: Immediate command publishing

#### Usage Example
```python
from robot_code.move import RobotController

# Create controller
controller = RobotController(
    max_linear=0.5,      # 0.5 m/s max speed
    max_angular=1.5,     # 1.5 rad/s max turn rate
    use_stamped=True,     # Use timestamped messages
    frame_id='base_link'  # Robot frame
)

# Set movement
controller.set_movement(throttle=0.8, angle=30.0)  # 80% forward, 30°/s turn

# Stop robot
controller.stop()
```

### 2. Client Mode Function

TCP client that connects to the control server and receives commands.

#### Key Features
- **Automatic Connection**: Connects to server automatically
- **Command Processing**: Receives and processes JSON commands
- **Reconnection**: Automatically reconnects on connection loss
- **Error Handling**: Graceful handling of connection issues

#### Parameters

##### Connection Parameters
- **`host`**: Server host address (default: '10.205.3.47')
  - **Impact**: Server IP address to connect to
  - **Tuning**: Must match server configuration
  - **Range**: Valid IP addresses

- **`port`**: Server port (default: 6969)
  - **Impact**: Server port to connect to
  - **Tuning**: Must match server configuration
  - **Range**: 1024-65535

##### Control Parameters
- **`max_linear`**: Maximum linear speed (default: 0.5 m/s)
- **`max_angular`**: Maximum angular speed (default: 1.5 rad/s)
- **`use_stamped`**: Use timestamped messages (default: True)
- **`frame_id`**: Reference frame ID (default: 'base_link')

#### Usage Example
```python
# Run in client mode
python3 robot_code/move.py client 192.168.1.100 6969

# Or use default server
python3 robot_code/move.py client
```

### 3. Standalone Demo Mode

Interactive demo mode for testing robot movement without server.

#### Key Features
- **Interactive Control**: Manual command input
- **Demo Sequences**: Pre-programmed movement patterns
- **Testing**: Test robot movement capabilities

#### Usage Example
```python
# Run standalone demo
python3 robot_code/move.py

# Interactive commands
Throttle and Angle: 0.8 60  # 80% forward, 60°/s turn
Throttle and Angle: 0.0 0  # Stop
```

## Movement Control Parameters

### Speed Tuning

#### For Precise Movement
```python
# Conservative settings
controller = RobotController(
    max_linear=0.3,      # 0.3 m/s max speed
    max_angular=1.0,     # 1.0 rad/s max turn rate
    rate_hz=15.0         # 15 Hz control loop
)
```

#### For Fast Movement
```python
# Aggressive settings
controller = RobotController(
    max_linear=0.8,      # 0.8 m/s max speed
    max_angular=2.5,     # 2.5 rad/s max turn rate
    rate_hz=25.0         # 25 Hz control loop
)
```

#### For Obstacle-Rich Environments
```python
# Safe settings
controller = RobotController(
    max_linear=0.4,      # 0.4 m/s max speed
    max_angular=1.2,     # 1.2 rad/s max turn rate
    rate_hz=20.0         # 20 Hz control loop
)
```

### Control Loop Tuning

#### High Responsiveness
```python
# High frequency control
controller.rate_hz = 30.0  # 30 Hz
controller.max_linear = 0.6
controller.max_angular = 2.0
```

#### Smooth Movement
```python
# Lower frequency for smoothness
controller.rate_hz = 15.0  # 15 Hz
controller.max_linear = 0.4
controller.max_angular = 1.0
```

#### Balanced Performance
```python
# Balanced settings
controller.rate_hz = 20.0  # 20 Hz
controller.max_linear = 0.5
controller.max_angular = 1.5
```

## Common Issues and Solutions

### Connection Issues

#### 1. Cannot Connect to Server
**Symptoms**: Connection timeout or refused
**Solutions**:
- Check server IP and port
- Verify network connectivity
- Check firewall settings
- Test with ping/telnet

#### 2. Connection Drops Frequently
**Symptoms**: Intermittent disconnections
**Solutions**:
- Check network stability
- Increase timeout values
- Check server load
- Monitor connection quality

#### 3. Commands Not Received
**Symptoms**: Robot not responding to commands
**Solutions**:
- Check command format
- Verify JSON parsing
- Test with simple commands
- Check ROS 2 connection

### Movement Issues

#### 1. Robot Too Slow
**Symptoms**: Robot moves very slowly
**Solutions**:
- Increase `max_linear` and `max_angular`
- Check rate_hz setting
- Verify ROS 2 publishing
- Check robot hardware limits

#### 2. Robot Too Fast/Jerky
**Symptoms**: Robot moves too fast or jerky
**Solutions**:
- Decrease `max_linear` and `max_angular`
- Lower rate_hz
- Check for command spikes
- Verify smooth command flow

#### 3. Robot Not Turning
**Symptoms**: Robot only moves forward/backward
**Solutions**:
- Check angular speed limits
- Verify turn rate commands
- Check ROS 2 angular.z publishing
- Test with manual commands

#### 4. Robot Drifts
**Symptoms**: Robot doesn't stop when commanded
**Solutions**:
- Check stop command handling
- Verify zero command publishing
- Check robot hardware
- Monitor command flow

### ROS 2 Issues

#### 1. No Twist Messages Published
**Symptoms**: No movement commands in ROS 2
**Solutions**:
- Check ROS 2 node status
- Verify topic publishing
- Check message format
- Test with rostopic echo

#### 2. Wrong Message Format
**Symptoms**: Robot receives but doesn't execute commands
**Solutions**:
- Check Twist message format
- Verify coordinate system
- Check frame_id setting
- Test with different message types

#### 3. High CPU Usage
**Symptoms**: High CPU consumption
**Solutions**:
- Reduce rate_hz
- Optimize control loop
- Check for infinite loops
- Monitor system resources

## Performance Optimization

### For High-Speed Applications
```python
# High performance settings
controller = RobotController(
    max_linear=0.8,      # Fast linear speed
    max_angular=2.5,      # Fast angular speed
    rate_hz=30.0,         # High frequency
    use_stamped=True      # Timestamped messages
)
```

### For Precision Applications
```python
# High precision settings
controller = RobotController(
    max_linear=0.3,       # Controlled speed
    max_angular=1.0,      # Smooth turns
    rate_hz=20.0,         # Balanced frequency
    use_stamped=True      # Timestamped messages
)
```

### For Real-Time Performance
```python
# Real-time optimized settings
controller = RobotController(
    max_linear=0.5,       # Balanced speed
    max_angular=1.5,      # Balanced turns
    rate_hz=25.0,         # High frequency
    use_stamped=True      # Timestamped messages
)
```

## Integration with Other Modules

### With Server Module
- Receives commands from server
- Sends status to server
- Handles connection management
- Processes command format

### With ROS 2 System
- Publishes Twist messages
- Integrates with robot navigation
- Handles coordinate frames
- Manages message timing

### With Robot Hardware
- Controls robot motors
- Handles safety limits
- Manages power consumption
- Provides feedback

## Best Practices

### 1. Speed Configuration
- Start with conservative limits
- Test with actual robot
- Gradually increase limits
- Monitor robot behavior

### 2. Control Loop
- Use appropriate frequency
- Monitor CPU usage
- Check for timing issues
- Test with different rates

### 3. Safety
- Implement emergency stop
- Monitor robot status
- Handle connection failures
- Provide user feedback

### 4. Performance
- Monitor resource usage
- Optimize control loop
- Check for bottlenecks
- Test with different loads

## Troubleshooting Checklist

### Connection Issues
1. Check server IP and port
2. Verify network connectivity
3. Test with ping/telnet
4. Check firewall settings
5. Monitor connection status

### Movement Issues
1. Check speed limits
2. Verify command format
3. Test with manual commands
4. Check ROS 2 publishing
5. Monitor robot response

### Performance Issues
1. Monitor CPU usage
2. Check control loop frequency
3. Optimize algorithms
4. Test with different settings
5. Profile application

### ROS 2 Issues
1. Check node status
2. Verify topic publishing
3. Check message format
4. Test with rostopic
5. Monitor system resources

## Usage Examples

### Basic Robot Control
```python
# Create controller
controller = RobotController(max_linear=0.5, max_angular=1.5)

# Move forward
controller.set_movement(throttle=1.0, angle=0.0)

# Turn left
controller.set_movement(throttle=0.5, angle=30.0)

# Stop
controller.stop()
```

### Client Mode
```bash
# Connect to server
python3 robot_code/move.py client 192.168.1.100 6969

# Use default server
python3 robot_code/move.py client
```

### Standalone Demo
```bash
# Run demo
python3 robot_code/move.py

# Interactive control
Throttle and Angle: 0.8 60
Throttle and Angle: 0.0 0
```

### Custom Configuration
```python
# Custom settings
controller = RobotController(
    max_linear=0.6,      # 0.6 m/s max speed
    max_angular=2.0,     # 2.0 rad/s max turn rate
    use_stamped=True,    # Use timestamped messages
    frame_id='base_link' # Robot frame
)
```

## Safety Considerations

### Emergency Stop
- Always implement emergency stop
- Monitor robot status
- Handle connection failures
- Provide manual override

### Speed Limits
- Set appropriate speed limits
- Test with actual robot
- Consider environment safety
- Monitor robot behavior

### Error Handling
- Handle connection failures
- Process invalid commands
- Monitor robot status
- Provide user feedback
