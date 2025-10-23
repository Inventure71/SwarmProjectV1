# OptiTrack Module Documentation

## Overview
The OptiTrack module provides real-time robot position tracking using OptiTrack motion capture system. It handles UDP communication, coordinate transformations, and multi-robot tracking.

## Components

### 1. RobotTracker Class (`tracker.py`)

Main tracking system that listens to UDP ports for pose data and updates Robot objects in real-time.

#### Key Features
- **Multi-robot tracking**: Handles multiple robots simultaneously
- **Real-time updates**: Thread-safe position updates
- **Coordinate transformation**: Converts OptiTrack coordinates to robot coordinates
- **Automatic robot creation**: Creates Robot instances from configuration

#### Critical Calibration Parameters

##### Coordinate System Parameters
- **`x_offset`**: X-axis offset in millimeters (default: -250mm)
  - **Impact**: Shifts robot position along X-axis
  - **Tuning**: Adjust to center robot in workspace
  - **Range**: -1000 to +1000mm

- **`y_offset`**: Y-axis offset in millimeters (default: -200mm)
  - **Impact**: Shifts robot position along Y-axis
  - **Tuning**: Adjust to center robot in workspace
  - **Range**: -1000 to +1000mm

- **`scale_factor`**: Scale factor from mm to meters (default: 1/40.0)
  - **Impact**: Converts OptiTrack units to meters
  - **Tuning**: Adjust based on OptiTrack calibration
  - **Range**: 0.001 to 0.1 (typical: 0.01-0.05)

##### Coordinate Transformation Parameters
- **`flip_x`**: Flip X-axis direction (default: True)
  - **Impact**: Inverts X-axis orientation
  - **Tuning**: Set based on OptiTrack setup
  - **Values**: True/False

- **`flip_y`**: Flip Y-axis direction (default: False)
  - **Impact**: Inverts Y-axis orientation
  - **Tuning**: Set based on OptiTrack setup
  - **Values**: True/False

- **`invert_yaw`**: Invert yaw angle (default: False)
  - **Impact**: Inverts rotation direction
  - **Tuning**: Set based on robot orientation
  - **Values**: True/False

- **`yaw_offset`**: Yaw angle offset in degrees (default: 180°)
  - **Impact**: Rotates robot coordinate system
  - **Tuning**: Align robot front with desired direction
  - **Range**: 0° to 360°

- **`frame_rotation_deg`**: Frame rotation in degrees (default: 0°)
  - **Impact**: Rotates entire coordinate system
  - **Tuning**: Align coordinate system with workspace
  - **Range**: 0° to 360°

#### Methods
- **`start()`**: Start tracking threads for all robots
- **`stop()`**: Stop all tracking threads
- **`get_all_positions()`**: Get positions of all tracked robots
- **`get_robot(name)`**: Get specific robot by name

#### Usage Example
```python
from optitrack.tracker import RobotTracker

# Robot configuration
robot_config = {
    'umh_2': {'ip': '192.168.1.2', 'port': 9876},
    'umh_3': {'ip': '192.168.1.3', 'port': 9877}
}

# Create tracker
tracker = RobotTracker(robot_config)

# Start tracking
tracker.start()

# Get positions
positions = tracker.get_all_positions()
for name, (x, y, yaw) in positions.items():
    print(f"{name}: x={x:.3f}, y={y:.3f}, yaw={yaw:.3f}")
```

### 2. UDP Monitor (`udp_monitor.py`)

Utility for monitoring UDP traffic and debugging OptiTrack communication.

#### Key Features
- **Port range monitoring**: Listen on multiple UDP ports
- **Packet inspection**: View raw UDP packets
- **Debugging tool**: Helps diagnose communication issues
- **Real-time display**: Shows packet timestamps and content

#### Usage
```bash
# Monitor ports 9860-9900
python3 src/optitrack/udp_monitor.py 9860 9900
```

## Calibration and Setup

### Initial OptiTrack Setup

#### 1. Coordinate System Alignment
```python
# Example calibration for different setups
tracker = RobotTracker(robot_config)

# For standard setup (robot front facing +Y)
tracker.x_offset = -250
tracker.y_offset = -200
tracker.scale_factor = 1/40.0
tracker.flip_x = True
tracker.flip_y = False
tracker.invert_yaw = False
tracker.yaw_offset = 180
tracker.frame_rotation_deg = 0

# For inverted setup (robot front facing -Y)
tracker.flip_x = False
tracker.flip_y = True
tracker.yaw_offset = 0

# For rotated workspace (45° rotation)
tracker.frame_rotation_deg = 45
```

#### 2. Scale Factor Calibration
```python
# Measure known distance in OptiTrack
# If 1 meter = 40mm in OptiTrack units
tracker.scale_factor = 1.0 / 40.0  # 0.025

# If 1 meter = 100mm in OptiTrack units  
tracker.scale_factor = 1.0 / 100.0  # 0.01
```

#### 3. Offset Calibration
```python
# Place robot at known position (e.g., origin)
# Adjust offsets to match expected coordinates
tracker.x_offset = -250  # Adjust until robot shows x=0
tracker.y_offset = -200  # Adjust until robot shows y=0
```

### Common Calibration Issues

#### 1. Robot Position Incorrect
**Symptoms**: Robot appears in wrong location
**Solutions**:
- Adjust `x_offset` and `y_offset`
- Check `scale_factor` calculation
- Verify OptiTrack coordinate system

#### 2. Robot Orientation Wrong
**Symptoms**: Robot facing wrong direction
**Solutions**:
- Adjust `yaw_offset` (try 0°, 90°, 180°, 270°)
- Toggle `invert_yaw` (True/False)
- Check `flip_x` and `flip_y` settings

#### 3. Coordinate System Misaligned
**Symptoms**: Robot moves in wrong direction relative to commands
**Solutions**:
- Adjust `frame_rotation_deg`
- Check `flip_x` and `flip_y` combinations
- Verify robot orientation in OptiTrack

#### 4. Scale Issues
**Symptoms**: Robot moves wrong distance
**Solutions**:
- Recalculate `scale_factor`
- Measure known distance in OptiTrack
- Verify OptiTrack calibration

### Advanced Calibration Parameters

#### For Different Robot Orientations
```python
# Robot facing +X direction
tracker.yaw_offset = 90
tracker.flip_x = False
tracker.flip_y = False

# Robot facing -X direction  
tracker.yaw_offset = 270
tracker.flip_x = False
tracker.flip_y = False

# Robot facing +Y direction
tracker.yaw_offset = 0
tracker.flip_x = True
tracker.flip_y = False

# Robot facing -Y direction
tracker.yaw_offset = 180
tracker.flip_x = True
tracker.flip_y = False
```

#### For Different Workspace Orientations
```python
# 90° rotated workspace
tracker.frame_rotation_deg = 90

# 180° rotated workspace
tracker.frame_rotation_deg = 180

# 270° rotated workspace
tracker.frame_rotation_deg = 270
```

## Troubleshooting

### Connection Issues

#### 1. No UDP Packets Received
**Symptoms**: No position updates, no packet messages
**Solutions**:
- Check OptiTrack is streaming data
- Verify UDP port configuration
- Check network connectivity
- Use UDP monitor to verify packets
- Check firewall settings

#### 2. Intermittent Position Updates
**Symptoms**: Position updates stop/start randomly
**Solutions**:
- Check OptiTrack tracking quality
- Verify rigid body visibility
- Check network stability
- Increase UDP timeout values
- Monitor packet loss

#### 3. Wrong Robot Positions
**Symptoms**: Robot appears in incorrect location
**Solutions**:
- Recalibrate coordinate system
- Check OptiTrack rigid body setup
- Verify coordinate transformations
- Test with known positions

### Performance Issues

#### 1. Slow Position Updates
**Symptoms**: Delayed position updates
**Solutions**:
- Check OptiTrack frame rate
- Verify network latency
- Monitor UDP packet frequency
- Check system performance

#### 2. Position Jitter
**Symptoms**: Robot position jumps around
**Solutions**:
- Improve OptiTrack tracking quality
- Add position smoothing
- Check for reflections
- Verify rigid body mounting

#### 3. Coordinate Drift
**Symptoms**: Position slowly drifts over time
**Solutions**:
- Recalibrate OptiTrack system
- Check for temperature changes
- Verify rigid body stability
- Monitor OptiTrack calibration

## Integration with Other Modules

### With Core Module
- Creates and updates Robot instances
- Provides thread-safe position access
- Handles coordinate transformations

### With Control Module
- Provides position data for path following
- Enables real-time position feedback
- Supports delay compensation

### With UI Module
- Displays robot positions on maps
- Provides real-time position updates
- Enables visual tracking

## Best Practices

### 1. Calibration
- Always calibrate with robot at known positions
- Test with multiple positions and orientations
- Document calibration parameters
- Recalibrate after system changes

### 2. Network Setup
- Use dedicated network for OptiTrack
- Avoid network congestion
- Monitor packet loss and latency
- Use appropriate UDP buffer sizes

### 3. Tracking Quality
- Ensure good rigid body visibility
- Minimize reflections and occlusions
- Use appropriate marker sizes
- Monitor tracking confidence

### 4. Performance
- Monitor update rates (aim for 100+ Hz)
- Check for position jitter
- Verify coordinate accuracy
- Test with actual robot movements

## Configuration Examples

### Standard Setup
```python
# Standard configuration for most setups
tracker = RobotTracker(robot_config)
tracker.x_offset = -250
tracker.y_offset = -200
tracker.scale_factor = 1/40.0
tracker.flip_x = True
tracker.flip_y = False
tracker.invert_yaw = False
tracker.yaw_offset = 180
tracker.frame_rotation_deg = 0
```

### Inverted Setup
```python
# For inverted coordinate system
tracker.flip_x = False
tracker.flip_y = True
tracker.yaw_offset = 0
```

### Rotated Workspace
```python
# For 45° rotated workspace
tracker.frame_rotation_deg = 45
```

### Multiple Robots
```python
# Configuration for multiple robots
robot_config = {
    'robot_1': {'ip': '192.168.1.2', 'port': 9876},
    'robot_2': {'ip': '192.168.1.3', 'port': 9877},
    'robot_3': {'ip': '192.168.1.4', 'port': 9878}
}
tracker = RobotTracker(robot_config)
```

## Monitoring and Debugging

### UDP Monitor Usage
```bash
# Monitor specific port range
python3 src/optitrack/udp_monitor.py 9870 9880

# Check for packet reception
# Look for messages like: [12:34:56.789] port=9876 from=192.168.1.2:12345
```

### Position Monitoring
```python
# Monitor robot positions
while True:
    positions = tracker.get_all_positions()
    for name, (x, y, yaw) in positions.items():
        print(f"{name}: x={x:.3f}, y={y:.3f}, yaw={yaw:.3f}")
    time.sleep(0.1)
```

### Debugging Tips
1. Use UDP monitor to verify packet reception
2. Check OptiTrack streaming status
3. Verify network connectivity
4. Monitor position update frequency
5. Test with known robot positions
6. Check coordinate transformations
7. Verify rigid body setup in OptiTrack
