import threading
import math
import time


class Robot:
    """
    Represents a robot with position tracking capabilities.
    Thread-safe for real-time position updates from OptiTrack.
    """
    
    def __init__(self, initial_x=0.0, initial_y=0.0, initial_yaw=0.0, username="", ip="", port=None, robot_type="real"):
        """
        Initialize a Robot instance.
        
        Args:
            initial_x: Initial x position
            initial_y: Initial y position
            initial_yaw: Initial yaw angle (in radians)
            username: Robot username/identifier
            ip: Robot IP address
            port: Communication port (for OptiTrack UDP)
            robot_type: Type of robot ("real" or "dummy")
        """
        self.start_x = initial_x
        self.start_y = initial_y
        self.start_yaw = initial_yaw

        self._lock = threading.Lock()
        self.x = initial_x
        self.y = initial_y
        self.yaw = initial_yaw

        self.username = username
        self.ip = ip
        self.port = port
        self.robot_type = robot_type

        self.max_turn_rate = 1.5
        self.max_forward_speed = 0.5

    def set_location(self, x, y, yaw=0):
        """
        Manually set the robot's location.
        
        Args:
            x: X position
            y: Y position
            yaw: Yaw angle (default: 0)
        """
        with self._lock:
            self.x = x
            self.y = y
            self.yaw = yaw
        print(f"[Robot {self.username or self.ip}] Location set to: x={x:.4f}, y={y:.4f}, yaw={yaw:.4f}")

    def update_position(self, x, y, yaw):
        """
        Update the robot's position (called by tracker).
        Thread-safe method for real-time updates from OptiTrack.
        
        Args:
            x: New x position
            y: New y position
            yaw: New yaw angle
        """
        with self._lock:
            self.x = x
            self.y = y
            self.yaw = yaw

    def get_position(self):
        """
        Get the current robot position in a thread-safe manner.
        
        Returns:
            tuple: (x, y, yaw)
        """
        with self._lock:
            return (self.x, self.y, self.yaw)

    def reset_to_start(self):
        """Reset robot to initial starting position."""
        self.set_location(self.start_x, self.start_y, self.start_yaw)

    def __repr__(self):
        """String representation of the robot."""
        pos = self.get_position()
        return f"Robot(username='{self.username}', type='{self.robot_type}', pos=({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}))"


class DummyRobot(Robot):
    """Dummy robot that simulates movement without hardware."""
    
    def __init__(self, *args, **kwargs):
        kwargs['robot_type'] = 'dummy'
        super().__init__(*args, **kwargs)
        self._sim_thread = None
        self._sim_running = False
        self._current_throttle = 0.0
        self._current_turn_rate = 0.0
        self._last_update = time.time()
    
    def start_simulation(self):
        """Start position simulation thread."""
        if self._sim_thread is None or not self._sim_thread.is_alive():
            self._sim_running = True
            self._sim_thread = threading.Thread(target=self._simulate_movement, daemon=True)
            self._sim_thread.start()
    
    def stop_simulation(self):
        """Stop simulation thread."""
        self._sim_running = False
        if self._sim_thread:
            self._sim_thread.join(timeout=1.0)
    
    def set_command(self, throttle, turn_rate_deg):
        """Set movement command for simulation."""
        with self._lock:
            self._current_throttle = max(-1.0, min(1.0, throttle))
            self._current_turn_rate = -math.radians(turn_rate_deg)
    
    def _simulate_movement(self):
        """Simulate robot movement based on commands."""
        while self._sim_running:
            current_time = time.time()
            dt = current_time - self._last_update
            self._last_update = current_time
            
            with self._lock:
                if abs(self._current_throttle) > 0.01 or abs(self._current_turn_rate) > 0.01:
                    linear_vel = self._current_throttle * self.max_forward_speed
                    angular_vel = self._current_turn_rate
                    
                    self.yaw += angular_vel * dt
                    self.yaw = (self.yaw + math.pi) % (2 * math.pi) - math.pi
                    
                    self.x += linear_vel * math.cos(self.yaw) * dt
                    self.y += linear_vel * math.sin(self.yaw) * dt
            
            time.sleep(0.05)


def create_robot(robot_type="real", robot_ip="", robot_port=None, username="", 
                 initial_x=0.0, initial_y=0.0, initial_yaw=0.0):
    """
    Factory function to create a Robot instance.
    
    Args:
        robot_type: Type of robot ("real" or "dummy")
        robot_ip: IP address of the robot
        robot_port: Communication port
        username: Robot username/identifier
        initial_x: Initial x position (default: 0.0)
        initial_y: Initial y position (default: 0.0)
        initial_yaw: Initial yaw angle (default: 0.0)
    
    Returns:
        Robot or DummyRobot instance
    """
    if robot_type == "dummy":
        robot = DummyRobot(
            initial_x=initial_x,
            initial_y=initial_y,
            initial_yaw=initial_yaw,
            username=username,
            ip=robot_ip or "dummy",
            port=robot_port
        )
        robot.start_simulation()
    else:
        robot = Robot(
            initial_x=initial_x,
            initial_y=initial_y,
            initial_yaw=initial_yaw,
            username=username,
            ip=robot_ip,
            port=robot_port,
            robot_type="real"
        )
    
    print(f"[Factory] Created {robot_type} robot: {username}")
    return robot
