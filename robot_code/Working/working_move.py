# file: move.py
# Simple ROS 2 robot movement controller for cmd_vel
# - Uses direction value (0 or 1) and angle for movement
# - Turn while moving (linear.x + angular.z)
#
# Usage:
#   direction: 0 = stop, 1 = move forward
#   angle: angle in radians to turn (positive = left, negative = right)
#   max_linear: maximum linear speed (m/s)
#   max_angular: maximum angular speed (rad/s)

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
import time
import threading
import socket
import json
import sys

def calculate_movement(direction, angle):
    """
    Calculate linear and angular velocities based on direction and angle.
    
    Args:
        direction: 0 = stop, 1 = move forward
        angle: angle in radians (positive = left turn, negative = right turn)
    
    Returns:
        tuple: (linear_velocity, angular_velocity)
    """
    # Linear component depends on direction; angular is passed through (factor)
    linear_vel = 1.0 if direction == 1 else 0.0
    angular_vel = angle
    return (linear_vel, angular_vel)

class RobotController(Node):
    def __init__(self, max_linear=0.5, max_angular=1.5, use_stamped=True, frame_id='base_link'):
        super().__init__('robot_controller')
        self.use_stamped = use_stamped
        self.frame_id = frame_id
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )
        if self.use_stamped:
            self.publisher_ = self.create_publisher(TwistStamped, '/cmd_vel', qos)
        else:
            self.publisher_ = self.create_publisher(Twist, '/cmd_vel', qos)

        # Tunables
        self.max_lin = max_linear   # m/s
        self.max_ang = max_angular  # rad/s
        self.lin = 0.0
        self.ang = 0.0

        self.rate_hz = 20.0
        self.turn_burst_sec = 0.8  # duration for in-place turn when over max
        self.timer = self.create_timer(1.0 / self.rate_hz, self._on_timer)
        self.get_logger().info("Robot controller started.")

    def _on_timer(self):
        # Publish current twist continuously
        if self.use_stamped:
            msg = TwistStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.frame_id
            msg.twist.linear.x = max(-self.max_lin, min(self.max_lin, self.lin))
            msg.twist.angular.z = max(-self.max_ang, min(self.max_ang, self.ang))
            self.publisher_.publish(msg)
        else:
            msg = Twist()
            msg.linear.x = max(-self.max_lin, min(self.max_lin, self.lin))
            msg.angular.z = max(-self.max_ang, min(self.max_ang, self.ang))
            self.publisher_.publish(msg)

    def set_movement(self, direction, angle):
        """
        Set robot movement based on direction and angle in degrees per second.
        
        Args:
            direction: 0 = stop, 1 = move forward (will be coerced to int 0/1)
            angle: desired yaw rate in degrees per second (positive = left, negative = right)
        """
        # Coerce incoming values to correct types
        try:
            dir_val = int(direction)
        except (TypeError, ValueError):
            dir_val = 0
        dir_val = 1 if dir_val == 1 else 0

        try:
            angle_val_deg = float(angle)
        except (TypeError, ValueError):
            angle_val_deg = 0.0

        # Convert degrees/sec to radians/sec and map to factor of max_ang
        angle_rate_rad = angle_val_deg * 3.141592653589793 / 180.0
        if self.max_ang > 0.0:
            angle_factor = angle_rate_rad / self.max_ang
        else:
            angle_factor = 0.0
        
        # Case 1: turn in place when direction == 0
        if dir_val == 0 and angle_rate_rad != 0.0:
            self.lin = 0.0
            # clamp to max
            self.ang = max(-self.max_ang, min(self.max_ang, angle_rate_rad))
            self._print_status()
            self._publish_immediate()
            return

        # Case 2: requested rate exceeds max while moving forward -> turn in place briefly, then go
        if dir_val == 1 and abs(angle_rate_rad) > self.max_ang + 1e-6:
            # stop linear, turn at max rate in requested direction
            self.lin = 0.0
            self.ang = self.max_ang if angle_rate_rad > 0.0 else -self.max_ang
            self._print_status()
            self._publish_immediate()
            # perform brief in-place turn burst
            t_end = time.time() + self.turn_burst_sec
            while time.time() < t_end and rclpy.ok():
                rclpy.spin_once(self, timeout_sec=0.0)
                time.sleep(1.0 / self.rate_hz)
            # then proceed forward straight
            self.lin = self.max_lin
            self.ang = 0.0
            self._print_status()
            self._publish_immediate()
            return

        # Normal case: move with requested factor (clamped)
        if angle_factor > 1.0:
            angle_factor = 1.0
        elif angle_factor < -1.0:
            angle_factor = -1.0
        lin_dir, ang_dir = calculate_movement(dir_val, angle_factor)
        self.lin = lin_dir * self.max_lin
        self.ang = ang_dir * self.max_ang
        self._print_status()
        self._publish_immediate()

    def _publish_immediate(self):
        # Publish once immediately (helps with responsiveness during blocking operations)
        if self.use_stamped:
            msg = TwistStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.frame_id
            msg.twist.linear.x = self.lin
            msg.twist.angular.z = self.ang
            self.publisher_.publish(msg)
        else:
            msg = Twist()
            msg.linear.x = self.lin
            msg.angular.z = self.ang
            self.publisher_.publish(msg)

    def stop(self):
        """Stop the robot."""
        self.lin = 0.0
        self.ang = 0.0
        self._print_status()

    def _print_status(self):
        print(f"\rmax_lin: {self.max_lin:.2f} m/s | max_ang: {self.max_ang:.2f} rad/s | "
              f"lin: {self.lin:.2f} | ang: {self.ang:.2f}      ",
              end='', flush=True)

def run_client_mode(host='10.205.3.47', port=6969):
    """
    Client mode: connects to a remote server and receives commands.
    Commands are JSON: {"direction": 0/1, "angle": degrees_per_sec}
    """
    rclpy.init()
    node = RobotController(max_linear=0.5, max_angular=1.5, use_stamped=True, frame_id='base_link')
    
    # Spin in background
    spinner = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spinner.start()
    
    print(f"[CLIENT] Connecting to server at {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        sock.connect((host, port))
        print(f"[CLIENT] Connected to {host}:{port}")
        sock.settimeout(0.1)
        
        buffer = ""
        while rclpy.ok():
            try:
                data = sock.recv(1024)
                if not data:
                    print("[CLIENT] Server disconnected")
                    break
                    
                buffer += data.decode('utf-8')
                # Process complete JSON messages (newline-delimited)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            cmd = json.loads(line)
                            direction = cmd.get('direction', 0)
                            angle = cmd.get('angle', 0.0)
                            node.set_movement(direction=direction, angle=angle)
                        except json.JSONDecodeError as e:
                            print(f"[CLIENT] JSON decode error: {e}")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[CLIENT] Error: {e}")
                break
                
    except KeyboardInterrupt:
        print("\n[CLIENT] Stopping...")
    except Exception as e:
        print(f"[CLIENT] Connection error: {e}")
    finally:
        node.stop()
        sock.close()
        if node.use_stamped:
            stop = TwistStamped()
            stop.header.stamp = node.get_clock().now().to_msg()
            stop.header.frame_id = node.frame_id
            node.publisher_.publish(stop)
        else:
            stop = Twist()
            node.publisher_.publish(stop)
        rclpy.shutdown()
        print("[CLIENT] Exiting.")

def main():
    """
    Main entry point: can run in client mode or standalone demo mode.
    Usage:
      python3 move.py                    # standalone demo
      python3 move.py client [host] [port]  # connect to server
    """
    if len(sys.argv) > 1 and sys.argv[1] == 'client':
        host = sys.argv[2] if len(sys.argv) > 2 else '10.205.3.47'
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 6969
        run_client_mode(host, port)
    else:
        # Standalone demo mode with interactive input
        rclpy.init()
        node = RobotController(max_linear=0.5, max_angular=1.5, use_stamped=True, frame_id='base_link')

        try:
            print("Moving forward for 2s")
            node.set_movement(direction=1, angle=0.0)
            t_end = time.time() + 2.0
            while time.time() < t_end and rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.0)
                time.sleep(0.1)

            print("Turning left for 2s")
            node.set_movement(direction=1, angle=0.3)
            t_end = time.time() + 2.0
            while time.time() < t_end and rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.0)
                time.sleep(0.1)

            print("Stopping")
            node.set_movement(direction=0, angle=0.0)
            # Spin in background so timers keep firing during interactive input
            spinner = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
            spinner.start()
            print("\nStandalone mode: Enter commands (direction angle)")
            print("Example: '1 60' = forward with 60 deg/s turn")
            while True:
                direction, angle = input("Direction and Angle: ").split()
                node.set_movement(direction=direction, angle=angle)
        except KeyboardInterrupt:
            print("\nStopping robot...")
            node.stop()
        finally:
            if node.use_stamped:
                stop = TwistStamped()
                stop.header.stamp = node.get_clock().now().to_msg()
                stop.header.frame_id = node.frame_id
                node.publisher_.publish(stop)
            else:
                stop = Twist()
                node.publisher_.publish(stop)
            rclpy.shutdown()
            print("Exiting.")

if __name__ == '__main__':
    main()
