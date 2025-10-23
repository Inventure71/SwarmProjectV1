#!/usr/bin/env python3
import socket
import threading
import time
import sys
from pathlib import Path
import math

# Add the parent directory to the path to allow importing modules
sys.path.append(str(Path(__file__).resolve().parent.parent))
from core.robot import Robot, create_robot

class RobotTracker:
    """
    Listens to UDP ports for pose data and updates Robot objects in real-time.
    """

    def __init__(self, robot_config_mapping: dict[str, dict]):
        """
        Initializes the tracker.
        
        Args:
            robot_config_mapping: A dictionary mapping a robot's name/ID to its config dict.
                                 Each config dict should have 'ip' and 'port' keys.
                                 Example: {'umh_2': {'ip': '192.168.1.2', 'port': 9876}}
        """
        self.robot_config_mapping = robot_config_mapping
        self.robots = {
            name: create_robot(
                robot_type="real", 
                robot_ip=config['ip'],
                robot_port=config['port'],
                username=name
            ) 
            for name, config in robot_config_mapping.items()
        }
        self._should_exit = threading.Event()
        self._threads = []

        # OptiTrack calibration parameters
        self.x_offset = -250  # millimetres
        self.y_offset = -200  # millimetres
        self.scale_factor = 1 / 40.0  # mm -> m
        self.flip_x = True
        self.flip_y = False
        self.invert_yaw = False
        self.yaw_offset = 180
        self.frame_rotation_deg = 0
        self.frame_rotation_rad = math.radians(self.frame_rotation_deg)

    def _listener_thread(self, robot_name: str, port: int, host: str = "0.0.0.0"):
        """
        Internal thread function to listen on a port for a specific robot.
        Receives UDP packets in format: [x,y,z,w] where w is yaw angle.
        """
        robot = self.robots[robot_name]
        print(f"[Tracker: {robot_name}] 🎯 Starting listener on {host}:{port}")
        
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                print(f"[Tracker: {robot_name}] ✓ Successfully bound to port {port}")
            except OSError as e:
                print(f"[Tracker: {robot_name}] ❌ ERROR: Could not bind to port {port}. {e}")
                return

            s.settimeout(1.0)  # Timeout to allow checking the exit flag
            
            packet_count = 0
            last_report = time.time()
            
            while not self._should_exit.is_set():
                try:
                    data, addr = s.recvfrom(100)
                    packet_count += 1
                    
                    # Decode the message as string
                    msg = data.decode()
                    
                    # DEBUG: Show raw received data
                    if packet_count == 1:
                        print(f"[Tracker: {robot_name}] 📦 First packet from {addr}: '{msg}'")
                    
                    # Remove brackets and split by comma: [x,y,z,w] -> x,y,z,w
                    msg = msg.strip('[]')
                    x_raw, y_raw, z_raw, yaw_raw = map(float, msg.split(','))
                    
                    # Apply transformations
                    # Convert to metres
                    x = (x_raw + self.x_offset) * self.scale_factor
                    y = (y_raw + self.y_offset) * self.scale_factor
                    yaw = yaw_raw + self.yaw_offset # radians from OptiTrack

                    # Reflections invert orientation
                    if self.flip_x:
                        x = -x
                        yaw = math.pi - yaw
                    if self.flip_y:
                        y = -y
                        yaw = -yaw

                    if self.invert_yaw:
                        yaw = -yaw

                    # Rotate coordinate frame to align with UI axes
                    if abs(self.frame_rotation_rad) > 1e-9:
                        cos_r = math.cos(self.frame_rotation_rad)
                        sin_r = math.sin(self.frame_rotation_rad)
                        x_rot = x * cos_r - y * sin_r
                        y_rot = x * sin_r + y * cos_r
                        x, y = x_rot, y_rot
                        yaw += self.frame_rotation_rad

                    # Normalise yaw to [-pi, pi]
                    yaw = (yaw + math.pi) % (2 * math.pi) - math.pi
                    
                    robot.update_position(x, y, yaw)
                    
                    # Report every 2 seconds
                    now = time.time()
                    if now - last_report >= 2.0:
                        print(f"[Tracker: {robot_name}] 📍 Packets: {packet_count}, Current pos: x={x:.3f}, y={y:.3f}, yaw={math.degrees(yaw):.2f}°")
                        last_report = now

                except socket.timeout:
                    continue  # Loop again to check exit flag
                except Exception as e:
                    print(f"[Tracker: {robot_name}] ⚠️  Error parsing packet: {e}")
                    print(f"[Tracker: {robot_name}]     Raw data: {data}")

        print(f"[Tracker: {robot_name}] 🛑 Listener shut down (received {packet_count} packets total)")

    def start(self):
        """
        Starts the tracking threads for all robots.
        """
        if self._threads:
            print("Tracker is already running.")
            return

        print("Starting real-time robot trackers...")
        self._should_exit.clear()
        for name, config in self.robot_config_mapping.items():
            port = config['port']
            thread = threading.Thread(target=self._listener_thread, args=(name, port), daemon=True)
            self._threads.append(thread)
            thread.start()

    def stop(self):
        """
        Signals all tracking threads to stop.
        """
        print("Stopping robot trackers...")
        self._should_exit.set()
        for thread in self._threads:
            thread.join(timeout=2.0)
        self._threads = []
        print("All trackers have been stopped.")

    def get_all_positions(self):
        """
        Get positions of all tracked robots.
        
        Returns:
            dict: Dictionary mapping robot name to (x, y, yaw) tuple
        """
        return {name: robot.get_position() for name, robot in self.robots.items()}

    def get_robot(self, name):
        """
        Get a specific robot by name.
        
        Args:
            name: Robot name
        
        Returns:
            Robot instance or None if not found
        """
        return self.robots.get(name)

def main() -> int:
    """
    Example usage of the RobotTracker.
    """
    # --- CONFIGURATION ---
    # This dictionary defines which robots to track with their IP and UDP port.
    # The names should match the rigid body names from OptiTrack/ROS.
    ROBOT_CONFIG = {
        'umh_2': {'ip': '192.168.1.2', 'port': 9876},
        'umh_3': {'ip': '192.168.1.3', 'port': 9877},
        'umh_4': {'ip': '192.168.1.4', 'port': 9878},
        'umh_5': {'ip': '192.168.1.5', 'port': 9880},
    }
    # ---------------------

    tracker = RobotTracker(ROBOT_CONFIG)
    tracker.start()

    print("\nRobot positions will be updated in the background.")
    print("Displaying current robot positions every 2 seconds. Press Ctrl+C to stop.")

    try:
        while True:
            print("\n--- Current Robot States ---")
            for name, robot in tracker.robots.items():
                pos = robot.get_position()
                print(f"  - {name}: Position(x,y): ({pos[0]:.4f}, {pos[1]:.4f}), Yaw: {pos[2]:.4f} rad")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nCaught interrupt signal.")
    finally:
        tracker.stop()

    print("Ending...")

    return 0

if __name__ == "__main__":
    sys.exit(main())


"""
other ports to save but not use yet

"umh_2": {"ip": "192.168.1.2", "port": 9876},
"umh_3": {"ip": "192.168.1.3", "port": 9877},
"umh_4": {"ip": "192.168.1.4", "port": 9878},

"""
