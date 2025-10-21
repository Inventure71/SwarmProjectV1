import threading


class Robot:
    """
    Represents a robot with position tracking capabilities.
    Thread-safe for real-time position updates from OptiTrack.
    """
    
    def __init__(self, initial_x=0.0, initial_y=0.0, initial_yaw=0.0, username="", ip="", port=None):
        """
        Initialize a Robot instance.
        
        Args:
            initial_x: Initial x position
            initial_y: Initial y position
            initial_yaw: Initial yaw angle (in radians)
            username: Robot username/identifier
            ip: Robot IP address
            port: Communication port (for OptiTrack UDP)
        """
        # For later use (reset capability)
        self.start_x = initial_x
        self.start_y = initial_y
        self.start_yaw = initial_yaw

        # Current position (thread-safe access)
        self._lock = threading.Lock()
        self.x = initial_x
        self.y = initial_y
        self.yaw = initial_yaw

        self.username = username
        self.ip = ip
        self.port = port

        self.max_turn_rate = 1.5 # rad/s
        self.max_forward_speed = 0.5 # m/s

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
        return f"Robot(username='{self.username}', ip='{self.ip}', pos=({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}))"


def create_robot(robot_type="real", robot_ip="", robot_port=None, username="", 
                 initial_x=0.0, initial_y=0.0, initial_yaw=0.0):
    """
    Factory function to create a Robot instance.
    
    Args:
        robot_type: Type of robot ("real" or "simulated")
        robot_ip: IP address of the robot
        robot_port: Communication port
        username: Robot username/identifier
        initial_x: Initial x position (default: 0.0)
        initial_y: Initial y position (default: 0.0)
        initial_yaw: Initial yaw angle (default: 0.0)
    
    Returns:
        Robot: A new Robot instance
    """
    robot = Robot(
        initial_x=initial_x,
        initial_y=initial_y,
        initial_yaw=initial_yaw,
        username=username,
        ip=robot_ip,
        port=robot_port
    )
    
    print(f"[Factory] Created {robot_type} robot: {robot_ip}")
    return robot
