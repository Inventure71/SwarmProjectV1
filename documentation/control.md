# Control Module Documentation

## Overview
The control module provides robot movement control and path following capabilities. It includes TCP communication for robot commands and sophisticated path following algorithms with delay compensation.

## Components

### 1. RobotController Class (`robot_controller.py`)

TCP server for robot communication and command broadcasting.

#### Key Features
- **TCP Server**: Listens for robot connections on configurable port
- **Command Broadcasting**: Sends movement commands to connected robots
- **Thread-safe**: Handles multiple robot connections safely
- **Legacy Support**: Maintains compatibility with older robot protocols

#### Parameters

##### Server Configuration
- **`host`**: Server host address (default: '0.0.0.0')
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
- **`start_server()`**: Start TCP server
- **`send_command(throttle, angle)`**: Send command to robot
- **`shutdown()`**: Stop server and close connections

#### Usage Example
```python
from control.robot_controller import RobotController

# Create controller
controller = RobotController(host='0.0.0.0', port=6969)

# Start server
controller.start_server()

# Send commands
controller.send_command(throttle=0.5, angle=30.0)  # Forward at 50% with 30°/s turn
controller.send_command(throttle=0.0, angle=0.0)   # Stop
```

### 2. PathFollower Class (`path_follower.py`)

Advanced path following controller with delay compensation and sophisticated waypoint management.

#### Key Features
- **Delay Compensation**: Predicts future position to account for tracking delays
- **Waypoint Management**: Handles complex paths with multiple waypoints
- **Path Simplification**: Reduces waypoint complexity for smoother motion
- **Adaptive Speed**: Adjusts speed based on path curvature and approach distance

#### Critical Parameters for Robot Movement

##### Waypoint Control Parameters
- **`waypoint_tolerance`**: Distance to consider waypoint reached (default: 0.15m)
  - **Impact**: How close robot must get to waypoint
  - **Tuning**: 
    - Smaller values (0.05-0.10m) = more precise positioning
    - Larger values (0.20-0.30m) = faster path completion
    - **Range**: 0.05 - 0.50m

- **`turn_in_place_threshold`**: Angle error to turn in place (default: 30°)
  - **Impact**: When robot stops to turn before moving
  - **Tuning**:
    - Smaller values (15-25°) = more frequent stops, precise orientation
    - Larger values (35-45°) = smoother motion, less precise
    - **Range**: 10° - 60°

##### Speed Control Parameters
- **`proportional_gain`**: Turn rate control gain (default: 3.0)
  - **Impact**: How aggressively robot corrects heading
  - **Tuning**:
    - Lower values (1.0-2.0) = smoother, slower corrections
    - Higher values (3.0-5.0) = more responsive, potentially oscillatory
    - **Range**: 0.5 - 10.0

- **`max_turn_rate`**: Maximum turn rate (default: 86°/s)
  - **Impact**: Maximum angular velocity
  - **Tuning**:
    - Lower values (30-60°/s) = smoother turns
    - Higher values (80-120°/s) = faster corrections
    - **Range**: 10° - 180°/s

- **`curvature_speed_gain`**: Speed reduction for tight turns (default: 1.2)
  - **Impact**: How much speed is reduced during turns
  - **Tuning**:
    - Lower values (0.5-1.0) = less speed reduction
    - Higher values (1.5-2.0) = more speed reduction for safety
    - **Range**: 0.0 - 3.0

- **`min_speed_ratio`**: Minimum throttle while moving (default: 0.05)
  - **Impact**: Minimum forward speed to maintain motion
  - **Tuning**:
    - Lower values (0.02-0.05) = can stop more easily
    - Higher values (0.08-0.15) = maintains better momentum
    - **Range**: 0.0 - 0.3

##### Delay Compensation Parameters
- **`use_prediction`**: Enable position prediction (default: True)
  - **Impact**: Compensates for tracking delays
  - **Tuning**: Keep enabled for better performance

- **`estimated_delay_ms`**: Estimated tracking delay (default: 100ms)
  - **Impact**: How far ahead to predict position
  - **Tuning**:
    - Lower values (50-80ms) = less compensation
    - Higher values (120-200ms) = more compensation
    - **Range**: 0 - 500ms

##### Path Optimization Parameters
- **`path_simplification_tolerance`**: Max deviation for path simplification (default: 0.05m)
  - **Impact**: How much path can be simplified
  - **Tuning**:
    - Lower values (0.02-0.05m) = more precise paths
    - Higher values (0.10-0.20m) = smoother, simpler paths
    - **Range**: 0.0 - 0.5m

- **`min_waypoint_separation`**: Minimum distance between waypoints (default: 0.12m)
  - **Impact**: Minimum spacing between processed waypoints
  - **Tuning**:
    - Lower values (0.05-0.10m) = more waypoints, precise paths
    - Higher values (0.15-0.25m) = fewer waypoints, smoother motion
    - **Range**: 0.05 - 0.5m

##### Approach Control Parameters
- **`slow_down_distance`**: Distance to start slowing down (default: 0.5m)
  - **Impact**: When to begin deceleration
  - **Tuning**:
    - Lower values (0.2-0.4m) = later deceleration
    - Higher values (0.6-1.0m) = earlier deceleration
    - **Range**: 0.1 - 2.0m

- **`waypoint_approach_slowdown`**: Distance for approach slowdown (default: 0.4m)
  - **Impact**: Distance over which to reduce speed near waypoints
  - **Tuning**:
    - Lower values (0.2-0.3m) = shorter slowdown zone
    - Higher values (0.5-0.8m) = longer slowdown zone
    - **Range**: 0.1 - 1.5m

#### Methods
- **`set_waypoints(waypoints)`**: Set new path
- **`update_position(x, y, yaw)`**: Update robot position
- **`compute_command()`**: Get next movement command
- **`is_complete()`**: Check if path is finished
- **`get_state()`**: Get current state information

#### Usage Example
```python
from control.path_follower import PathFollower

# Create path follower with custom parameters
follower = PathFollower(
    waypoints=[(1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    waypoint_tolerance=0.15,
    turn_in_place_threshold=30.0,
    proportional_gain=3.0,
    max_turn_rate=86.0,
    use_prediction=True,
    estimated_delay_ms=100
)

# Control loop
while not follower.is_complete():
    # Update position
    follower.update_position(robot_x, robot_y, robot_yaw)
    
    # Get command
    throttle, turn_rate = follower.compute_command()
    
    # Send to robot
    controller.send_command(throttle, turn_rate)
```

### 3. PositionPredictor Class

Internal class for position prediction and delay compensation.

#### Parameters
- **`alpha`**: Exponential smoothing factor (default: 0.3)
  - **Impact**: How much to weight new vs. old velocity estimates
  - **Tuning**:
    - Lower values (0.1-0.2) = smoother estimates, slower response
    - Higher values (0.4-0.6) = more responsive, potentially noisy
    - **Range**: 0.1 - 0.8

## Movement Parameter Tuning Guide

### For Smooth, Precise Movement
```python
follower = PathFollower(
    waypoint_tolerance=0.10,           # Precise positioning
    turn_in_place_threshold=25.0,     # More frequent stops
    proportional_gain=2.0,            # Gentle corrections
    max_turn_rate=60.0,              # Moderate turn speed
    curvature_speed_gain=1.5,        # More speed reduction
    min_speed_ratio=0.08,            # Maintain momentum
    slow_down_distance=0.6,          # Early deceleration
    estimated_delay_ms=120            # Conservative delay
)
```

### For Fast, Aggressive Movement
```python
follower = PathFollower(
    waypoint_tolerance=0.20,           # Less precise
    turn_in_place_threshold=40.0,      # Fewer stops
    proportional_gain=4.0,             # Aggressive corrections
    max_turn_rate=100.0,              # Fast turns
    curvature_speed_gain=1.0,         # Less speed reduction
    min_speed_ratio=0.05,             # Can stop easily
    slow_down_distance=0.3,           # Late deceleration
    estimated_delay_ms=80              # Less delay compensation
)
```

### For Obstacle-Rich Environments
```python
follower = PathFollower(
    waypoint_tolerance=0.12,           # Balanced precision
    turn_in_place_threshold=35.0,      # Moderate stops
    proportional_gain=2.5,             # Balanced corrections
    max_turn_rate=70.0,               # Controlled turns
    curvature_speed_gain=1.8,         # Significant speed reduction
    min_speed_ratio=0.06,             # Good momentum
    slow_down_distance=0.8,           # Early deceleration
    waypoint_approach_slowdown=0.6,    # Extended slowdown
    estimated_delay_ms=100             # Standard delay
)
```

## Common Issues and Solutions

### Robot Movement Problems

#### 1. Robot Oscillates Around Waypoint
**Symptoms**: Robot overshoots and corrects repeatedly
**Solutions**:
- Decrease `proportional_gain` (try 1.5-2.0)
- Increase `waypoint_tolerance` (try 0.20-0.25)
- Decrease `max_turn_rate` (try 50-60°/s)

#### 2. Robot Too Slow to Reach Waypoints
**Symptoms**: Robot moves very slowly or stops frequently
**Solutions**:
- Increase `min_speed_ratio` (try 0.08-0.12)
- Decrease `curvature_speed_gain` (try 0.8-1.2)
- Increase `max_turn_rate` (try 80-100°/s)
- Decrease `turn_in_place_threshold` (try 20-25°)

#### 3. Robot Cuts Corners Too Much
**Symptoms**: Robot doesn't follow path precisely
**Solutions**:
- Decrease `waypoint_tolerance` (try 0.08-0.12)
- Decrease `path_simplification_tolerance` (try 0.02-0.04)
- Increase `min_waypoint_separation` (try 0.15-0.20)

#### 4. Robot Stops Too Far From Waypoints
**Symptoms**: Robot stops before reaching target
**Solutions**:
- Increase `waypoint_tolerance` (try 0.20-0.30)
- Decrease `slow_down_distance` (try 0.3-0.4)
- Check `segment_pass_distance` and `segment_pass_lateral_factor`

#### 5. Robot Too Jerky/Jerky Motion
**Symptoms**: Sudden speed changes, rough movement
**Solutions**:
- Decrease `proportional_gain` (try 1.5-2.5)
- Increase `estimated_delay_ms` (try 120-150)
- Decrease `max_turn_rate` (try 50-70°/s)
- Increase `waypoint_approach_slowdown` (try 0.5-0.7)

### Connection Issues

#### 1. Robot Not Responding to Commands
**Solutions**:
- Check TCP connection (port 6969)
- Verify robot is running client code
- Check network connectivity
- Verify command format (JSON with throttle/angle)

#### 2. Commands Not Reaching Robot
**Solutions**:
- Check server is running
- Verify port configuration
- Check firewall settings
- Test with barebones server first

## Performance Optimization

### For High-Speed Applications
- Use `SimplePathFollower` for basic path following
- Disable prediction (`use_prediction=False`)
- Increase `max_turn_rate` and `max_forward_speed`
- Use larger `waypoint_tolerance`

### For Precision Applications
- Enable all advanced features
- Use smaller tolerances
- Increase delay compensation
- Use more waypoints in path

### For Real-Time Performance
- Monitor control loop frequency (aim for 10-20 Hz)
- Use appropriate delay compensation
- Balance precision vs. speed parameters
- Test with actual robot hardware
