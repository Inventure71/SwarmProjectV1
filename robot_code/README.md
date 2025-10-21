## Robot Movement Controller System

This system provides remote robot control via a client-server architecture:
- **Robot Client** (`move.py`): Runs on the robot, receives commands and publishes to ROS 2 `cmd_vel`
- **Server** (CLI or UI): Runs on a remote computer, sends movement commands to connected robots

### Control Interface

Commands use:
- **direction**: 0 (stop) or 1 (move forward)
- **angle**: turn rate in degrees per second (positive = left, negative = right)

The robot continuously publishes `geometry_msgs/Twist` or `TwistStamped` messages to `/cmd_vel` at 20 Hz.

### How it Works

- The node class `RobotController` exposes `set_movement(direction, angle)` which maps inputs to internal targets and clamps output by `max_linear` and `max_angular`.
- A timer publishes the current `Twist` at 20 Hz:
  - `linear.x` = clamped forward speed
  - `angular.z` = clamped yaw rate
- The helper `calculate_movement(direction, angle)` converts inputs into normalized linear/angular directives:
  - `direction == 0` → `(0.0, 0.0)` (stop)
  - `direction == 1` → `(1.0, angle)` (move forward and turn by angle)

### Interface

- Topic: `cmd_vel` (`geometry_msgs/Twist` or `geometry_msgs/TwistStamped`)
- Rate: 20 Hz
- Parameters (constructor):
  - `max_linear` (default 0.5 m/s)
  - `max_angular` (default 1.5 rad/s)
  - `use_stamped` (default `False`) → publish `TwistStamped` when `True`
  - `frame_id` (default `base_link`) → header frame when using stamped
  - QoS: BEST_EFFORT, KEEP_LAST, depth=10 (matches many mobile bases)

### Quick Start

#### 1. Start the Server (on your computer)

**Option A: Barebones CLI Server**
```bash
python3 robot/server_barebones.py [port]
```
Simple command-line interface. Enter commands like:
- `1 0` - Move forward straight
- `1 60` - Move forward, turn left 60 deg/s
- `0 90` - Stop linear, turn in place 90 deg/s
- `0 0` - Full stop

**Option B: Advanced UI Server**
```bash
python3 robot/server_ui.py [port]
```
Graphical interface with:
- **Speed slider**: Control linear velocity (0-0.5 m/s)
- **Joystick**: Push up = forward, left/right = turn
- **Emergency stop button**

#### 2. Connect Robot Client (on the robot)

```bash
python3 robot/move.py client [server_host] [port]
```

Example:
```bash
# Connect to server at 192.168.1.100:5000
python3 robot/move.py client 192.168.1.100 5000

# Connect to localhost (default)
python3 robot/move.py client
```

The robot will connect to the server and respond to commands in real-time.

#### 3. Standalone Mode (no server)

```bash
python3 robot/move.py
```
Runs a demo sequence then allows manual input directly on the robot.

#### Control it programmatically (same process)

```python
from robot.move import RobotController
import rclpy

rclpy.init()
node = RobotController(max_linear=0.5, max_angular=1.5, use_stamped=True, frame_id='base_link')

# Move forward with a slight left turn
node.set_movement(direction=1, angle=0.3)

# ... later, stop
node.set_movement(direction=0, angle=0.0)

rclpy.spin(node)
# On shutdown, ensure zero cmd (type depends on use_stamped)
if node.use_stamped:
    from geometry_msgs.msg import TwistStamped
    zero = TwistStamped()
    zero.header.stamp = node.get_clock().now().to_msg()
    zero.header.frame_id = node.frame_id
    node.publisher_.publish(zero)
else:
    from geometry_msgs.msg import Twist
    node.publisher_.publish(Twist())
rclpy.shutdown()
```

#### Control from another node (different process)

If you keep `move.py` running (spinning), you can call services or publish higher-level commands from another node by importing `RobotController` and interacting with it directly within the same process, or simply publish `Twist` messages to `cmd_vel` yourself.

Example of publishing a `Twist` directly (bypassing `move.py`):

```python
from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node

class SimplePublisher(Node):
    def __init__(self):
        super().__init__('simple_pub')
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.timer = self.create_timer(0.05, self.tick)

    def tick(self):
        msg = Twist()
        msg.linear.x = 0.5  # m/s
        msg.angular.z = 0.3 # rad/s
        self.pub.publish(msg)

```

### Architecture

**Communication Protocol:**
- TCP socket connection (default port 5000)
- JSON messages, newline-delimited: `{"direction": 0/1, "angle": deg_per_sec}\n`
- Server broadcasts commands to all connected robot clients
- Multiple robots can connect to one server

**Special Behaviors:**
- **Turn in place**: Set `direction=0` with non-zero `angle` to rotate without moving forward
- **Over-limit turning**: If requested turn rate exceeds `max_angular`, robot stops, performs brief in-place turn burst, then proceeds forward straight
- **Auto-stop**: Robots send stop command on disconnect or Ctrl+C

### Notes

- Positive `angle` turns left; negative turns right
- `angle` is in degrees per second (converted internally to rad/s)
- Maximum turn rate: ~86 deg/s (1.5 rad/s default), adjustable via `max_angular`
- Actual commanded values are clamped by `max_linear` and `max_angular`
- QoS: BEST_EFFORT, KEEP_LAST, depth=10 (matches many mobile bases)
- Ensure your robot subscribes to `/cmd_vel` and accepts `TwistStamped`

### Troubleshooting

- **Robot doesn't move**: Check that ROS 2 is running, `/cmd_vel` topic exists, and `use_stamped` matches your robot's expectation
- **Connection refused**: Ensure server is running first and firewall allows port 5000
- **Laggy control**: Check network latency; UI server updates at 10Hz, increase if needed


