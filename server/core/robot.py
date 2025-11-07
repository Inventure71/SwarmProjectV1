import threading
import math
import time
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class PathData:
    """Path data container."""
    waypoints: List[Tuple[float, float]]
    updated_at: float


class Robot:
    """
    Represents a robot with all related functionality consolidated.
    Thread-safe for real-time position updates from OptiTrack.
    Contains path following, racing config, and command management.
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
        
        # Racing configuration
        from core.racing_config import RacingConfig
        self.racing_config = RacingConfig(username)
        
        # Path following state
        self.path_follower: Optional['PathFollower'] = None
        self.path_data: Optional[PathData] = None
        self.last_throttle: float = 0.0
        
        # Reference to ROS controller (set externally)
        self._ros_controller: Optional[object] = None

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
    
    def set_ros_controller(self, controller):
        """Set the ROS controller reference for command sending."""
        self._ros_controller = controller
    
    def set_path(self, waypoints: List[Tuple[float, float]]) -> None:
        """
        Set path waypoints for this robot.
        
        Args:
            waypoints: List of (x, y) tuples in meters
        """
        processed = [(float(x), float(y)) for x, y in waypoints]
        self.path_data = PathData(waypoints=processed, updated_at=time.time())
    
    def clear_path(self) -> None:
        """Clear the path and stop path following."""
        self.stop_path_following()
        self.path_data = None
    
    def start_path_following(self, path_follower_params: Dict) -> bool:
        """
        Start path following for this robot.
        
        Args:
            path_follower_params: Dictionary of parameters for PathFollower initialization
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.path_follower is not None:
            return False
        
        if not self.path_data or not self.path_data.waypoints:
            return False
        
        from control.path_follower import PathFollower
        
        # Merge racing config into params
        params = dict(path_follower_params)
        params['lateral_offset'] = self.racing_config.lateral_offset
        params['speed_multiplier'] = self.racing_config.speed_multiplier
        
        follower = PathFollower(
            waypoints=list(self.path_data.waypoints),
            **params
        )
        follower.loop_enabled = self.racing_config.loop_path
        
        self.path_follower = follower
        return True
    
    def stop_path_following(self) -> None:
        """Stop path following and reset the follower."""
        if self.path_follower is not None:
            self.path_follower.reset()
            self.path_follower = None
        self.send_command(0.0, 0.0)
        self.last_throttle = 0.0
    
    def update_path_follower_position(self) -> None:
        """Update path follower with current robot position."""
        if self.path_follower is not None:
            x, y, yaw = self.get_position()
            self.path_follower.update_position(x, y, yaw)
    
    def compute_path_command(self) -> Optional[Tuple[float, float]]:
        """
        Compute command from path follower if active.
        
        Returns:
            Tuple of (throttle, turn_rate) or None if not following
        """
        if self.path_follower is None:
            return None
        
        if self.path_follower.is_complete():
            self.stop_path_following()
            return None
        
        return self.path_follower.compute_command()
    
    def send_command(self, throttle: float, turn_rate: float) -> bool:
        """
        Send command to robot.
        
        Args:
            throttle: Throttle value (-1.0 to 1.0)
            turn_rate: Turn rate in degrees per second
        
        Returns:
            True if command sent successfully
        """
        self.last_throttle = throttle
        
        if self.robot_type == "dummy":
            # For dummy robots, command is handled by simulation
            return True
        
        if self._ros_controller is None:
            return False
        
        return self._ros_controller.send_command(self.username, throttle, turn_rate)
    
    def is_following_path(self) -> bool:
        """Check if robot is currently following a path."""
        return self.path_follower is not None
    
    def get_path_follower_state(self) -> Optional[Dict]:
        """
        Get current path follower state.
        
        Returns:
            Dictionary with follower state or None if not following
        """
        if self.path_follower is None:
            return None
        
        state = self.path_follower.get_state()
        return {
            "waypoint_index": state.get("waypoint_index"),
            "total_waypoints": state.get("total_waypoints"),
            "distance_to_target": state.get("distance_to_target"),
            "throttle": self.last_throttle,
            "is_complete": self.path_follower.is_complete(),
        }
    
    def update_racing_config(self, offset: Optional[float] = None, 
                            speed: Optional[float] = None, 
                            loop: Optional[bool] = None) -> None:
        """
        Update racing configuration.
        
        Args:
            offset: Lateral offset in meters (optional)
            speed: Speed multiplier (optional)
            loop: Enable path looping (optional)
        """
        if offset is not None:
            self.racing_config.set_offset(offset)
        if speed is not None:
            self.racing_config.set_speed_multiplier(speed)
        if loop is not None:
            self.racing_config.set_loop(loop)
        
        # Update active path follower if exists
        if self.path_follower is not None:
            self.path_follower.set_lateral_offset(self.racing_config.lateral_offset)
            self.path_follower.speed_multiplier = self.racing_config.speed_multiplier
            self.path_follower.loop_enabled = self.racing_config.loop_path

    def __repr__(self):
        """String representation of the robot."""
        pos = self.get_position()
        following = "following" if self.is_following_path() else "idle"
        return f"Robot(username='{self.username}', type='{self.robot_type}', pos=({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}), {following})"


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
    
    def send_command(self, throttle: float, turn_rate: float) -> bool:
        """
        Send command to dummy robot (overrides base class).
        
        Args:
            throttle: Throttle value (-1.0 to 1.0)
            turn_rate: Turn rate in degrees per second
        
        Returns:
            True (always succeeds for dummy robots)
        """
        self.last_throttle = throttle
        self.set_command(throttle, turn_rate)
        return True
    
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
