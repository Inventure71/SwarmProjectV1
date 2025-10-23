# Core Module Documentation

## Overview
The core module provides fundamental robot representation and configuration management functionality. It serves as the foundation for all robot operations in the system.

## Components

### 1. Robot Class (`robot.py`)

The `Robot` class represents a single robot with position tracking capabilities and thread-safe operations for real-time updates from OptiTrack.

#### Key Features
- **Thread-safe position updates**: Uses threading locks for concurrent access
- **Position tracking**: Maintains current x, y, yaw coordinates
- **Reset capability**: Can return to initial starting position
- **Factory pattern**: Supports different robot types

#### Parameters

##### Movement Parameters
- **`max_turn_rate`**: Maximum turn rate in radians/second (default: 1.5 rad/s)
  - **Impact**: Controls how fast the robot can rotate
  - **Tuning**: Increase for more responsive turning, decrease for smoother motion
  - **Range**: 0.1 - 5.0 rad/s (typical values: 1.0-2.0)

- **`max_forward_speed`**: Maximum forward speed in meters/second (default: 0.5 m/s)
  - **Impact**: Limits maximum linear velocity
  - **Tuning**: Increase for faster movement, decrease for precision
  - **Range**: 0.1 - 2.0 m/s (typical values: 0.3-1.0)

##### Initialization Parameters
- **`initial_x`, `initial_y`**: Starting position coordinates (default: 0.0, 0.0)
- **`initial_yaw`**: Starting orientation in radians (default: 0.0)
- **`username`**: Robot identifier string
- **`ip`**: Robot IP address for communication
- **`port`**: Communication port for OptiTrack UDP

#### Methods

##### Position Management
- **`set_location(x, y, yaw=0)`**: Manually set robot position
- **`update_position(x, y, yaw)`**: Thread-safe position update (called by tracker)
- **`get_position()`**: Get current position tuple (x, y, yaw)
- **`reset_to_start()`**: Return to initial position

##### Factory Function
- **`create_robot(robot_type, robot_ip, robot_port, username, initial_x, initial_y, initial_yaw)`**: Create robot instances

#### Usage Example
```python
from core.robot import create_robot

# Create a real robot
robot = create_robot(
    robot_type="real",
    robot_ip="192.168.1.2",
    robot_port=9876,
    username="robot_1",
    initial_x=0.0,
    initial_y=0.0,
    initial_yaw=0.0
)

# Update position (typically called by tracker)
robot.update_position(1.5, 2.3, 0.785)

# Get current position
x, y, yaw = robot.get_position()
```

### 2. ConfigLoader Class (`config_loader.py`)

Singleton class for loading and managing robot configuration from `config.json`.

#### Key Features
- **Singleton pattern**: Ensures single configuration instance
- **JSON-based**: Loads configuration from JSON file
- **Robot mapping**: Maps robot names to IP/port settings
- **Error handling**: Graceful handling of missing config files

#### Configuration Structure
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

#### Methods
- **`get_robot_config()`**: Get all robot configurations
- **`get_robot_by_name(name)`**: Get specific robot configuration
- **`get_all_robot_names()`**: Get list of all robot names
- **`get_config()`**: Get entire configuration dictionary

#### Usage Example
```python
from core.config_loader import load_config

# Load configuration
config = load_config()

# Get robot configurations
robot_configs = config.get_robot_config()

# Get specific robot
robot_info = config.get_robot_by_name("umh_2")
```

## Configuration Parameters

### Robot Movement Tuning

#### Speed Parameters
- **Linear Speed**: Controlled by `max_forward_speed`
  - **Low values (0.1-0.3 m/s)**: Precise positioning, slower movement
  - **Medium values (0.4-0.7 m/s)**: Balanced speed and control
  - **High values (0.8-1.5 m/s)**: Fast movement, less precise

#### Angular Speed Parameters
- **Turn Rate**: Controlled by `max_turn_rate`
  - **Low values (0.5-1.0 rad/s)**: Smooth, controlled turns
  - **Medium values (1.0-2.0 rad/s)**: Responsive turning
  - **High values (2.0-4.0 rad/s)**: Quick, aggressive turns

### Common Issues and Solutions

#### Robot Movement Issues
1. **Robot too slow**: Increase `max_forward_speed`
2. **Robot too fast**: Decrease `max_forward_speed`
3. **Turning too slow**: Increase `max_turn_rate`
4. **Turning too fast/jerky**: Decrease `max_turn_rate`
5. **Position drift**: Check OptiTrack calibration parameters

#### Threading Issues
- **Position updates not thread-safe**: Ensure using `update_position()` method
- **Race conditions**: All position access goes through `get_position()`
- **Deadlocks**: Avoid calling position methods from multiple threads simultaneously

## Integration Points

### With OptiTrack Module
- Robot instances are created and updated by the tracker
- Position updates come from UDP packets
- Thread-safe communication between tracker and robot

### With Control Module
- Robot position is read by path followers
- Movement commands are sent to robot controllers
- State synchronization between modules

### With UI Module
- Robot positions are displayed on maps
- Configuration is loaded for robot selection
- Real-time position updates in UI

## Best Practices

1. **Always use thread-safe methods** for position access
2. **Initialize robots with appropriate speed limits** for your environment
3. **Use factory function** for consistent robot creation
4. **Handle configuration errors gracefully** in your application
5. **Reset robots to known positions** when starting new operations
6. **Monitor position updates** to ensure tracking is working correctly

## Troubleshooting

### Common Problems
1. **Robot not updating position**: Check OptiTrack connection and UDP ports
2. **Configuration not loading**: Verify `config.json` exists and is valid JSON
3. **Threading errors**: Ensure proper use of position methods
4. **Speed issues**: Adjust `max_forward_speed` and `max_turn_rate` parameters
5. **Position accuracy**: Check OptiTrack calibration and coordinate transformations
