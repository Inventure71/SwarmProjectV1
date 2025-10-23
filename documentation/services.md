# Services Module Documentation

## Overview
The services module provides high-level functionality for path management and motion recording. It handles saving/loading paths, recording robot motion via joystick control, and managing waypoint data.

## Components

### 1. PathService Class (`path_service.py`)

Service for managing robot paths, including saving, loading, and waypoint management.

#### Key Features
- **Path Management**: Handles waypoint creation and editing
- **File I/O**: Saves and loads paths in JSON format
- **Canvas Integration**: Draws paths on UI canvas
- **Coordinate Conversion**: Converts between canvas and world coordinates

#### Parameters

##### Path Creation Parameters
- **`canvas`**: Tkinter canvas widget for drawing
- **`world_to_canvas_func`**: Function to convert world to canvas coordinates
- **`canvas_to_world_func`**: Function to convert canvas to world coordinates

##### Waypoint Parameters
- **`path_points`**: List of canvas coordinates (x, y)
- **`recorded_positions`**: List of world coordinates (x, y) in meters

#### Methods
- **`add_waypoint(x, y, mode)`**: Add waypoint at canvas coordinates
- **`set_recorded_path(positions)`**: Set path from recorded positions
- **`clear_path()`**: Clear all waypoints and path
- **`get_waypoints_meters()`**: Get waypoints in world coordinates
- **`save_path(robot_name)`**: Save current path to file
- **`load_path()`**: Load path from file
- **`get_path_info()`**: Get information about current path

#### Usage Example
```python
from services.path_service import PathService

# Create path service
path_service = PathService(canvas, world_to_canvas, canvas_to_world)

# Add waypoints
path_service.add_waypoint(100, 200, "click")
path_service.add_waypoint(300, 400, "click")

# Save path
path_service.save_path("robot_1")

# Load path
path_service.load_path()
```

### 2. RecordingService Class (`recording_service.py`)

Service for recording robot motion via joystick control and managing recorded positions.

#### Key Features
- **Motion Recording**: Records robot positions during joystick control
- **Joystick Control**: Processes joystick input for robot movement
- **Position Sampling**: Records positions at configurable intervals
- **Real-time Visualization**: Shows recording trace on canvas

#### Critical Parameters for Robot Movement

##### Recording Parameters
- **`record_sample_distance`**: Minimum distance between recorded points (default: 0.05m)
  - **Impact**: Controls recording density
  - **Tuning**:
    - Smaller values (0.02-0.03m) = more detailed paths
    - Larger values (0.08-0.12m) = smoother, simpler paths
    - **Range**: 0.01 - 0.20m

##### Joystick Control Parameters
- **`max_turn_rate`**: Maximum turn rate for joystick control (default: 70°/s)
  - **Impact**: Controls how fast robot can turn via joystick
  - **Tuning**:
    - Lower values (30-50°/s) = smoother, more controlled turns
    - Higher values (80-120°/s) = more responsive, faster turns
    - **Range**: 10° - 180°/s

##### Control Parameters
- **`joystick_control_active`**: Enable/disable joystick control
- **`is_recording`**: Recording state flag
- **`last_recorded_position`**: Last recorded position for distance checking

#### Methods
- **`start_recording()`**: Start recording robot motion
- **`stop_recording()`**: Stop recording and return positions
- **`process_joystick_input(joy_x, joy_y)`**: Process joystick input
- **`get_recorded_positions()`**: Get list of recorded positions
- **`clear_recorded_positions()`**: Clear all recorded positions
- **`set_sample_distance(distance)`**: Set minimum distance between points
- **`set_max_turn_rate(rate)`**: Set maximum turn rate
- **`set_joystick_enabled(enabled)`**: Enable/disable joystick control

#### Usage Example
```python
from services.recording_service import RecordingService

# Create recording service
recording_service = RecordingService(
    robot_controller, robot_tracker, robot, canvas, world_to_canvas
)

# Start recording
recording_service.start_recording()

# Process joystick input
recording_service.process_joystick_input(0.5, 0.8)  # 50% right, 80% forward

# Stop recording
positions = recording_service.stop_recording()
```

## Movement Parameter Tuning

### For Precise Path Recording
```python
recording_service = RecordingService(...)

# High precision recording
recording_service.set_sample_distance(0.02)  # 2cm between points
recording_service.set_max_turn_rate(50.0)   # Moderate turn speed
```

### For Smooth Path Recording
```python
# Smooth recording with fewer points
recording_service.set_sample_distance(0.08)  # 8cm between points
recording_service.set_max_turn_rate(60.0)    # Smooth turns
```

### For Fast Path Recording
```python
# Fast recording for quick paths
recording_service.set_sample_distance(0.12)  # 12cm between points
recording_service.set_max_turn_rate(80.0)    # Responsive turns
```

## Path Management

### Creating Paths

#### Manual Waypoint Creation
```python
# Add waypoints manually
path_service.add_waypoint(100, 200, "click")  # Click mode
path_service.add_waypoint(300, 400, "draw")   # Draw mode

# Get waypoints in meters
waypoints = path_service.get_waypoints_meters()
```

#### Recorded Path Creation
```python
# Record robot motion
recording_service.start_recording()
# ... control robot with joystick ...
positions = recording_service.stop_recording()

# Set recorded path
path_service.set_recorded_path(positions)
```

### Saving and Loading Paths

#### Save Path
```python
# Save current path
success = path_service.save_path("robot_1")
if success:
    print("Path saved successfully")
```

#### Load Path
```python
# Load path from file
success = path_service.load_path()
if success:
    print("Path loaded successfully")
```

#### Path Information
```python
# Get path information
info = path_service.get_path_info()
print(f"Waypoints: {info['num_waypoints']}")
print(f"Recorded: {info['is_recorded']}")
```

## File Format

### Path JSON Structure
```json
{
    "robot": "robot_1",
    "timestamp": "2024-01-15T10:30:00",
    "waypoints": [
        [1.0, 0.0],
        [1.0, 1.0],
        [0.0, 1.0]
    ],
    "num_points": 3,
    "is_recorded": true
}
```

## Common Issues and Solutions

### Recording Issues

#### 1. Too Many/Few Recorded Points
**Symptoms**: Path too dense or too sparse
**Solutions**:
- Adjust `record_sample_distance`
- Smaller values = more points
- Larger values = fewer points

#### 2. Jerky Recording
**Symptoms**: Robot movement is jerky during recording
**Solutions**:
- Decrease `max_turn_rate`
- Use smoother joystick movements
- Check robot controller settings

#### 3. Recording Stops Unexpectedly
**Symptoms**: Recording stops before completion
**Solutions**:
- Check robot connection
- Verify joystick control is enabled
- Check for position tracking issues

### Path Management Issues

#### 1. Waypoints Not Saving
**Symptoms**: Path not saved to file
**Solutions**:
- Check file permissions
- Verify JSON format
- Check disk space
- Verify path has waypoints

#### 2. Path Not Loading
**Symptoms**: Path file not loading
**Solutions**:
- Check file format
- Verify JSON structure
- Check file path
- Verify waypoint coordinates

#### 3. Coordinate Conversion Issues
**Symptoms**: Waypoints in wrong location
**Solutions**:
- Check coordinate conversion functions
- Verify canvas scaling
- Check world coordinate system
- Test with known positions

### Joystick Control Issues

#### 1. Robot Not Responding to Joystick
**Symptoms**: No movement with joystick input
**Solutions**:
- Check `joystick_control_active` flag
- Verify robot controller connection
- Check joystick input values
- Verify control parameters

#### 2. Robot Moving Too Fast/Slow
**Symptoms**: Inappropriate speed response
**Solutions**:
- Adjust `max_turn_rate`
- Check joystick input scaling
- Verify robot controller settings
- Check speed limits

#### 3. Robot Turning Too Much/Little
**Symptoms**: Inappropriate turn response
**Solutions**:
- Adjust `max_turn_rate`
- Check joystick input processing
- Verify turn rate scaling
- Test with different joystick values

## Performance Optimization

### For High-Frequency Recording
```python
# Optimize for frequent updates
recording_service.set_sample_distance(0.03)  # 3cm between points
recording_service.set_max_turn_rate(60.0)   # Moderate turn speed
```

### For Long-Duration Recording
```python
# Optimize for long recordings
recording_service.set_sample_distance(0.08)  # 8cm between points
recording_service.set_max_turn_rate(50.0)    # Smooth turns
```

### For Real-Time Performance
```python
# Optimize for real-time use
recording_service.set_sample_distance(0.05)  # 5cm between points
recording_service.set_max_turn_rate(70.0)    # Responsive turns
```

## Integration with Other Modules

### With UI Module
- Draws paths on canvas
- Handles user interactions
- Provides visual feedback
- Manages coordinate conversion

### With Control Module
- Sends commands to robot controller
- Processes joystick input
- Manages robot movement
- Handles control state

### With Core Module
- Uses robot position data
- Updates robot state
- Manages robot instances
- Handles position tracking

## Best Practices

### 1. Recording Quality
- Use appropriate sample distance
- Record at consistent speed
- Avoid sudden direction changes
- Test recording quality

### 2. Path Management
- Save paths regularly
- Use descriptive filenames
- Backup important paths
- Document path purpose

### 3. Joystick Control
- Use smooth joystick movements
- Avoid extreme inputs
- Test control responsiveness
- Monitor robot behavior

### 4. Performance
- Monitor recording frequency
- Check for position updates
- Verify control loop timing
- Test with actual robot

## Troubleshooting Checklist

### Recording Issues
1. Check robot connection
2. Verify joystick control enabled
3. Check sample distance setting
4. Monitor position updates
5. Test with simple movements

### Path Issues
1. Check coordinate conversion
2. Verify waypoint data
3. Test file I/O operations
4. Check JSON format
5. Validate path structure

### Control Issues
1. Check joystick input values
2. Verify robot controller
3. Check control parameters
4. Test with simple commands
5. Monitor robot response

### Performance Issues
1. Check update frequency
2. Monitor system resources
3. Verify network connectivity
4. Test with different settings
5. Check for bottlenecks
