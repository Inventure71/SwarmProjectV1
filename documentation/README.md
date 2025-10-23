# Robot Swarm Project Documentation

## Overview
This documentation provides comprehensive information about the robot swarm implementation, including detailed parameter descriptions for movement control, location tracking, and system configuration.

## Module Documentation

### [Core Module](core.md)
- **Robot Class**: Thread-safe robot representation with position tracking
- **ConfigLoader**: Configuration management and robot mapping
- **Key Parameters**: `max_turn_rate`, `max_forward_speed`, position tracking

### [Control Module](control.md)
- **RobotController**: TCP server for robot communication
- **PathFollower**: Advanced path following with delay compensation
- **Key Parameters**: `waypoint_tolerance`, `proportional_gain`, `max_turn_rate`, `curvature_speed_gain`

### [OptiTrack Module](optitrack.md)
- **RobotTracker**: Real-time position tracking from OptiTrack
- **UDP Monitor**: Network debugging and packet inspection
- **Key Parameters**: `x_offset`, `y_offset`, `scale_factor`, `flip_x`, `flip_y`, `yaw_offset`

### [Services Module](services.md)
- **PathService**: Path management and waypoint handling
- **RecordingService**: Motion recording via joystick control
- **Key Parameters**: `record_sample_distance`, `max_turn_rate`, joystick sensitivity

### [UI Module](ui.md)
- **UI Components**: Modern styled interface components
- **Virtual Joystick**: Intuitive robot control interface
- **Key Parameters**: Joystick size, sensitivity, visual feedback

### [Server Module](server.md)
- **BarebonesServer**: Command-line robot control server
- **AdvancedTrackingServer**: GUI server with real-time tracking
- **Key Parameters**: `max_speed`, `max_angle`, map bounds, update frequency

### [Robot Code Module](robot_code.md)
- **RobotController**: ROS 2-based robot movement control
- **Client Mode**: TCP client for server communication
- **Key Parameters**: `max_linear`, `max_angular`, `rate_hz`, control loop frequency

## Quick Reference

### Critical Movement Parameters

#### Speed Control
- **Linear Speed**: `max_forward_speed` (Core), `max_linear` (Robot Code)
- **Angular Speed**: `max_turn_rate` (Core), `max_angular` (Robot Code)
- **Control Frequency**: `rate_hz` (Robot Code), `update_interval` (Server)

#### Path Following
- **Waypoint Tolerance**: `waypoint_tolerance` (Control)
- **Turn Threshold**: `turn_in_place_threshold` (Control)
- **Control Gain**: `proportional_gain` (Control)
- **Speed Reduction**: `curvature_speed_gain` (Control)

#### Tracking
- **Coordinate Offsets**: `x_offset`, `y_offset` (OptiTrack)
- **Scale Factor**: `scale_factor` (OptiTrack)
- **Orientation**: `flip_x`, `flip_y`, `yaw_offset` (OptiTrack)

### Common Tuning Scenarios

#### For Precise Movement
```python
# Conservative settings for precision
max_forward_speed = 0.3  # m/s
max_turn_rate = 1.0     # rad/s
waypoint_tolerance = 0.10  # m
proportional_gain = 2.0
curvature_speed_gain = 1.5
```

#### For Fast Movement
```python
# Aggressive settings for speed
max_forward_speed = 0.8  # m/s
max_turn_rate = 2.5     # rad/s
waypoint_tolerance = 0.20  # m
proportional_gain = 4.0
curvature_speed_gain = 1.0
```

#### For Obstacle-Rich Environments
```python
# Safe settings for obstacles
max_forward_speed = 0.4  # m/s
max_turn_rate = 1.2     # rad/s
waypoint_tolerance = 0.15  # m
proportional_gain = 2.5
curvature_speed_gain = 1.8
```

## Troubleshooting Guide

### Robot Movement Issues

#### 1. Robot Too Slow
- Increase `max_forward_speed` and `max_linear`
- Decrease `curvature_speed_gain`
- Check `min_speed_ratio` in PathFollower

#### 2. Robot Too Fast/Jerky
- Decrease `max_forward_speed` and `max_linear`
- Increase `curvature_speed_gain`
- Lower `proportional_gain`

#### 3. Robot Oscillates
- Decrease `proportional_gain`
- Increase `waypoint_tolerance`
- Check `max_turn_rate` limits

#### 4. Robot Cuts Corners
- Decrease `waypoint_tolerance`
- Increase `path_simplification_tolerance`
- Check `min_waypoint_separation`

### Tracking Issues

#### 1. Wrong Position
- Adjust `x_offset` and `y_offset`
- Check `scale_factor` calculation
- Verify coordinate transformations

#### 2. Wrong Orientation
- Adjust `yaw_offset` (try 0°, 90°, 180°, 270°)
- Toggle `flip_x` and `flip_y`
- Check `invert_yaw` setting

#### 3. Position Jitter
- Improve OptiTrack tracking quality
- Add position smoothing
- Check for reflections

### Connection Issues

#### 1. Server Not Starting
- Check port availability
- Verify network configuration
- Test with different ports

#### 2. Robots Not Connecting
- Check network connectivity
- Verify robot client configuration
- Test with barebones server

#### 3. Commands Not Reaching Robots
- Check command format
- Verify robot client code
- Test with simple commands

## Configuration Files

### config.json
```json
{
    "ROBOT_CONFIG": {
        "robot_name": {
            "ip": "192.168.1.2",
            "port": 9876
        }
    }
}
```

### Robot Configuration
- **IP Address**: Robot's network address
- **Port**: UDP port for OptiTrack data
- **Name**: Robot identifier

## Getting Started

### 1. Setup
1. Configure `config.json` with robot information
2. Set up OptiTrack system
3. Install required dependencies
4. Test network connectivity

### 2. Calibration
1. Calibrate OptiTrack coordinate system
2. Adjust tracking parameters
3. Test with known positions
4. Verify coordinate transformations

### 3. Testing
1. Start with barebones server
2. Test robot connections
3. Verify command transmission
4. Test movement parameters

### 4. Optimization
1. Tune speed parameters
2. Adjust path following settings
3. Test with different scenarios
4. Monitor performance

## Best Practices

### 1. Parameter Tuning
- Start with conservative values
- Test with actual robot
- Gradually increase limits
- Monitor robot behavior

### 2. Safety
- Implement emergency stop
- Set appropriate speed limits
- Monitor robot status
- Handle connection failures

### 3. Performance
- Monitor update frequencies
- Optimize control loops
- Check resource usage
- Test with multiple robots

### 4. Maintenance
- Document parameter changes
- Test after modifications
- Monitor system performance
- Keep backups of working configurations

## Support

For additional help:
1. Check individual module documentation
2. Review troubleshooting guides
3. Test with known configurations
4. Monitor system logs
5. Verify network connectivity

## Version Information

- **Project**: Robot Swarm Project V1
- **Documentation**: Generated for current implementation
- **Last Updated**: Current session
- **Modules**: 7 documented modules
- **Parameters**: 50+ documented parameters
