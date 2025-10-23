# UI Module Documentation

## Overview
The UI module provides user interface components for robot control applications. It includes modern styled widgets, virtual joystick control, and canvas utilities for robot visualization.

## Components

### 1. UI Components (`components.py`)

Collection of modern styled UI components for robot control applications.

#### Key Features
- **Modern Styling**: Dark theme components with professional appearance
- **Consistent Design**: Unified styling across all components
- **Accessibility**: Proper contrast and visual feedback
- **Customizable**: Multiple style options for different use cases

#### Components

##### ModernButton Class
Modern styled button with multiple style options.

**Styles Available**:
- **`primary`**: Blue button for main actions
- **`success`**: Green button for positive actions
- **`warning`**: Orange button for caution actions
- **`danger`**: Red button for destructive actions
- **`secondary`**: Gray button for secondary actions

**Parameters**:
- **`text`**: Button text
- **`command`**: Callback function
- **`style`**: Button style (primary, success, warning, danger, secondary)

**Usage Example**:
```python
from ui.components import ModernButton

# Create buttons with different styles
start_btn = ModernButton(parent, "Start", command=start_robot, style="success")
stop_btn = ModernButton(parent, "Stop", command=stop_robot, style="danger")
```

##### StatusLabel Class
Status label with predefined color schemes.

**Status Types**:
- **`success`**: Green text for positive status
- **`warning`**: Orange text for caution
- **`error`**: Red text for errors
- **`info`**: Blue text for information
- **`neutral`**: Gray text for neutral status

**Usage Example**:
```python
from ui.components import StatusLabel

# Create status labels
status = StatusLabel(parent, "Robot Connected", status="success")
warning = StatusLabel(parent, "Low Battery", status="warning")
```

##### ModernFrame Class
Modern styled frame with optional title.

**Parameters**:
- **`title`**: Optional frame title
- **`parent`**: Parent widget

**Usage Example**:
```python
from ui.components import ModernFrame

# Create frames
control_frame = ModernFrame(parent, title="Robot Control")
status_frame = ModernFrame(parent, title="Status")
```

##### ModernScale Class
Modern styled scale widget for value selection.

**Parameters**:
- **`from_`**: Minimum value
- **`to`**: Maximum value
- **`resolution`**: Value resolution
- **`orient`**: Orientation (HORIZONTAL/VERTICAL)

**Usage Example**:
```python
from ui.components import ModernScale

# Create speed control slider
speed_scale = ModernScale(
    parent, from_=0.0, to=1.0, resolution=0.01, orient=tk.VERTICAL
)
```

##### ModernCheckbutton Class
Modern styled checkbutton for boolean options.

**Usage Example**:
```python
from ui.components import ModernCheckbutton

# Create checkboxes
enable_control = ModernCheckbutton(parent, text="Enable Control")
record_path = ModernCheckbutton(parent, text="Record Path")
```

##### CanvasGrid Class
Helper class for drawing grids on canvas.

**Parameters**:
- **`canvas`**: Tkinter canvas widget
- **`scale`**: Grid scale in pixels per meter (default: 100)
- **`width`**: Canvas width (default: 700)
- **`height`**: Canvas height (default: 700)

**Methods**:
- **`draw_grid()`**: Draw grid on canvas

**Usage Example**:
```python
from ui.components import CanvasGrid

# Create grid helper
grid = CanvasGrid(canvas, scale=100, width=800, height=600)
grid.draw_grid()
```

### 2. Virtual Joystick (`virtual_joystick.py`)

Custom Tkinter widget for intuitive robot control.

#### Key Features
- **Intuitive Control**: Visual joystick for robot movement
- **Real-time Feedback**: Immediate visual response
- **Configurable**: Adjustable size and behavior
- **Smooth Operation**: Smooth joystick movement

#### Parameters

##### Joystick Configuration
- **`size`**: Joystick size in pixels (default: 200)
  - **Impact**: Controls joystick sensitivity and visibility
  - **Tuning**: Larger sizes = easier control, smaller = more precise
  - **Range**: 100 - 400 pixels

- **`max_radius`**: Maximum joystick movement radius
  - **Impact**: Controls joystick sensitivity
  - **Tuning**: Larger radius = more precise control
  - **Range**: 50 - 150 pixels

##### Control Parameters
- **`joystick_x`**: X-axis value (-1.0 to 1.0)
  - **Impact**: Controls left/right movement
  - **Values**: -1.0 = left, 0.0 = center, 1.0 = right

- **`joystick_y`**: Y-axis value (-1.0 to 1.0)
  - **Impact**: Controls forward/backward movement
  - **Values**: -1.0 = backward, 0.0 = center, 1.0 = forward

#### Methods
- **`get_values()`**: Get current joystick values
- **`reset()`**: Reset joystick to center
- **`_on_press(event)`**: Handle mouse press
- **`_on_drag(event)`**: Handle mouse drag
- **`_on_release(event)`**: Handle mouse release

#### Usage Example
```python
from ui.virtual_joystick import VirtualJoystick

# Create joystick
joystick = VirtualJoystick(parent, size=250)

# Get joystick values
x, y = joystick.get_values()
print(f"X: {x}, Y: {y}")

# Reset joystick
joystick.reset()
```

## UI Design Parameters

### Color Scheme
The UI uses a dark theme with the following color palette:

- **Background**: `#1a1a1a` (Dark gray)
- **Secondary Background**: `#2a2a2a` (Medium gray)
- **Text**: `#fff` (White)
- **Primary**: `#2196F3` (Blue)
- **Success**: `#4CAF50` (Green)
- **Warning**: `#FFA500` (Orange)
- **Danger**: `#f44336` (Red)
- **Info**: `#00aaff` (Light blue)

### Typography
- **Font Family**: Arial
- **Font Sizes**: 8pt (small), 10pt (normal), 11pt (medium), 13pt (large), 18pt (title)
- **Font Weights**: Normal, Bold

### Spacing
- **Padding**: 5-15 pixels
- **Margins**: 10-20 pixels
- **Grid Spacing**: 100 pixels per meter

## Movement Control Integration

### Joystick Control Parameters

#### Sensitivity Tuning
```python
# High sensitivity (small movements)
joystick = VirtualJoystick(parent, size=150)

# Medium sensitivity (balanced)
joystick = VirtualJoystick(parent, size=200)

# Low sensitivity (large movements)
joystick = VirtualJoystick(parent, size=300)
```

#### Control Mapping
```python
# Get joystick values
x, y = joystick.get_values()

# Map to robot commands
throttle = y  # Forward/backward
turn_rate = -x * max_turn_rate  # Left/right (inverted)

# Send to robot
controller.send_command(throttle, turn_rate)
```

### Visual Feedback Parameters

#### Grid Configuration
```python
# Fine grid (1cm per pixel)
grid = CanvasGrid(canvas, scale=100, width=800, height=600)

# Coarse grid (2cm per pixel)
grid = CanvasGrid(canvas, scale=50, width=800, height=600)

# Very fine grid (0.5cm per pixel)
grid = CanvasGrid(canvas, scale=200, width=800, height=600)
```

#### Robot Visualization
```python
# Robot marker size
robot_size = 10  # pixels

# Robot colors
robot_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']

# Update frequency
update_interval = 100  # milliseconds
```

## Common Issues and Solutions

### UI Display Issues

#### 1. Components Not Visible
**Symptoms**: UI components not showing
**Solutions**:
- Check parent widget configuration
- Verify pack/grid placement
- Check color contrast
- Test with different themes

#### 2. Text Not Readable
**Symptoms**: Text too small or unclear
**Solutions**:
- Increase font size
- Check color contrast
- Verify font family
- Test with different backgrounds

#### 3. Layout Problems
**Symptoms**: Components overlapping or misaligned
**Solutions**:
- Check pack/grid parameters
- Verify parent widget size
- Test with different window sizes
- Check padding/margin settings

### Joystick Control Issues

#### 1. Joystick Not Responding
**Symptoms**: No response to mouse input
**Solutions**:
- Check event bindings
- Verify mouse events
- Test with different sizes
- Check parent widget focus

#### 2. Joystick Values Incorrect
**Symptoms**: Wrong values returned
**Solutions**:
- Check coordinate system
- Verify value scaling
- Test with known positions
- Check inversion settings

#### 3. Joystick Too Sensitive/Insensitive
**Symptoms**: Hard to control or not responsive
**Solutions**:
- Adjust joystick size
- Modify max_radius
- Check value scaling
- Test with different configurations

### Performance Issues

#### 1. UI Updates Too Slow
**Symptoms**: Laggy interface
**Solutions**:
- Reduce update frequency
- Optimize drawing operations
- Check system performance
- Use efficient rendering

#### 2. Memory Usage High
**Symptoms**: High memory consumption
**Solutions**:
- Limit canvas objects
- Clear old drawings
- Optimize data structures
- Check for memory leaks

## Best Practices

### 1. UI Design
- Use consistent styling
- Provide clear visual feedback
- Use appropriate colors
- Test with different screen sizes

### 2. Joystick Control
- Use appropriate joystick size
- Provide visual feedback
- Test control responsiveness
- Handle edge cases

### 3. Performance
- Limit update frequency
- Optimize drawing operations
- Use efficient algorithms
- Monitor resource usage

### 4. User Experience
- Provide clear instructions
- Use intuitive controls
- Test with actual users
- Handle errors gracefully

## Integration Examples

### Complete UI Setup
```python
import tkinter as tk
from ui.components import ModernButton, StatusLabel, ModernFrame
from ui.virtual_joystick import VirtualJoystick

# Create main window
root = tk.Tk()
root.title("Robot Control")
root.configure(bg='#1a1a1a')

# Create control frame
control_frame = ModernFrame(root, title="Robot Control")
control_frame.pack(pady=10)

# Create joystick
joystick = VirtualJoystick(control_frame, size=250)
joystick.pack(pady=10)

# Create buttons
start_btn = ModernButton(control_frame, "Start", command=start_robot, style="success")
start_btn.pack(pady=5)

stop_btn = ModernButton(control_frame, "Stop", command=stop_robot, style="danger")
stop_btn.pack(pady=5)

# Create status
status = StatusLabel(root, "Ready", status="info")
status.pack(pady=10)

# Start UI
root.mainloop()
```

### Joystick Control Loop
```python
def update_robot_control():
    # Get joystick values
    x, y = joystick.get_values()
    
    # Map to robot commands
    throttle = y
    turn_rate = -x * 70.0  # 70 degrees per second max
    
    # Send to robot
    if robot_controller.connected:
        robot_controller.send_command(throttle, turn_rate)
    
    # Schedule next update
    root.after(50, update_robot_control)

# Start control loop
update_robot_control()
```

### Grid and Canvas Setup
```python
from ui.components import CanvasGrid

# Create canvas
canvas = tk.Canvas(root, width=800, height=600, bg='#1a1a1a')
canvas.pack(pady=10)

# Create grid
grid = CanvasGrid(canvas, scale=100, width=800, height=600)
grid.draw_grid()

# Draw robot
def draw_robot(x, y, yaw):
    canvas.delete('robot')
    canvas.create_oval(x-10, y-10, x+10, y+10, fill='#4CAF50', tags='robot')
    canvas.create_line(x, y, x+20*math.cos(yaw), y+20*math.sin(yaw), 
                      fill='#4CAF50', width=3, tags='robot')
```

## Troubleshooting Checklist

### UI Issues
1. Check component initialization
2. Verify parent widget configuration
3. Test with different themes
4. Check event bindings
5. Verify layout parameters

### Joystick Issues
1. Check mouse event handling
2. Verify value calculation
3. Test with different sizes
4. Check coordinate system
5. Verify control mapping

### Performance Issues
1. Monitor update frequency
2. Check drawing operations
3. Verify memory usage
4. Test with different configurations
5. Profile application performance
