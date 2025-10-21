#!/usr/bin/env python3
"""
Reusable Path Following Controller
Implements path following logic with delay compensation that can be integrated into any system.
"""

import math
import time


class PositionPredictor:
    """Predicts future position based on velocity estimation."""
    
    def __init__(self, alpha=0.3):
        self.last_position = None
        self.last_time = None
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.velocity_yaw = 0.0
        self.alpha = alpha
        
    def update(self, x, y, yaw, timestamp=None):
        """Update velocity estimates using exponential smoothing."""
        if timestamp is None:
            timestamp = time.time()
            
        if self.last_position is not None:
            dt = timestamp - self.last_time
            # Only update if dt is reasonable (avoid division by very small numbers)
            if dt > 0.001 and dt < 10.0:  # Between 1ms and 10s
                vx = (x - self.last_position[0]) / dt
                vy = (y - self.last_position[1]) / dt
                vyaw = (yaw - self.last_position[2]) / dt
                
                # Clamp velocities to reasonable values (max 2 m/s, max 5 rad/s)
                vx = max(-2.0, min(2.0, vx))
                vy = max(-2.0, min(2.0, vy))
                vyaw = max(-5.0, min(5.0, vyaw))
                
                self.velocity_x = self.alpha * vx + (1 - self.alpha) * self.velocity_x
                self.velocity_y = self.alpha * vy + (1 - self.alpha) * self.velocity_y
                self.velocity_yaw = self.alpha * vyaw + (1 - self.alpha) * self.velocity_yaw
                
                # Safety check: reset if velocities become invalid
                if not (math.isfinite(self.velocity_x) and math.isfinite(self.velocity_y) and math.isfinite(self.velocity_yaw)):
                    self.reset()
        
        self.last_position = (x, y, yaw)
        self.last_time = timestamp
    
    def predict(self, x, y, yaw, dt_ahead):
        """Predict position dt_ahead seconds into the future."""
        # Clamp prediction time to reasonable values
        dt_ahead = max(0.0, min(1.0, dt_ahead))  # Max 1 second prediction
        
        pred_x = x + self.velocity_x * dt_ahead
        pred_y = y + self.velocity_y * dt_ahead
        pred_yaw = yaw + self.velocity_yaw * dt_ahead
        
        # Safety check: return current position if prediction is invalid
        if not (math.isfinite(pred_x) and math.isfinite(pred_y) and math.isfinite(pred_yaw)):
            return x, y, yaw
        
        return pred_x, pred_y, pred_yaw
    
    def reset(self):
        """Reset predictor state."""
        self.last_position = None
        self.last_time = None
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.velocity_yaw = 0.0


class PathFollower:
    """
    Path following controller with delay compensation.
    
    Usage:
        follower = PathFollower(waypoints=[(x1,y1), (x2,y2), ...])
        
        # In control loop:
        robot_x, robot_y, robot_yaw = get_robot_position()
        follower.update_position(robot_x, robot_y, robot_yaw)
        
        direction, turn_rate = follower.compute_command()
        send_command_to_robot(direction, turn_rate)
        
        if follower.is_complete():
            stop_robot()
    """
    
    def __init__(self, 
                 waypoints=None,
                 waypoint_tolerance=0.15,
                 turn_in_place_threshold=30.0,
                 proportional_gain=3.0,
                 max_turn_rate=86.0,
                 use_prediction=True,
                 estimated_delay_ms=100):
        """
        Initialize path follower.
        
        Args:
            waypoints: List of (x, y) tuples in meters
            waypoint_tolerance: Distance to consider waypoint reached (meters)
            turn_in_place_threshold: Angle error to turn in place before moving (degrees)
            proportional_gain: Proportional gain for turn rate control
            max_turn_rate: Maximum turn rate (degrees/second)
            use_prediction: Enable position prediction
            estimated_delay_ms: Estimated tracking delay (milliseconds)
        """
        self.waypoints = waypoints if waypoints is not None else []
        self.waypoint_tolerance = waypoint_tolerance
        self.turn_in_place_threshold = turn_in_place_threshold
        self.proportional_gain = proportional_gain
        self.max_turn_rate = max_turn_rate
        self.use_prediction = use_prediction
        self.estimated_delay_ms = estimated_delay_ms
        
        self.current_waypoint_index = 0
        self.current_position = None
        self.predictor = PositionPredictor()
        
    def set_waypoints(self, waypoints):
        """Set new waypoints and reset to beginning."""
        self.waypoints = waypoints
        self.current_waypoint_index = 0
        self.predictor.reset()  # Reset predictor when setting new waypoints
        
    def add_waypoint(self, x, y):
        """Add a waypoint to the path."""
        self.waypoints.append((x, y))
        
    def clear_waypoints(self):
        """Clear all waypoints."""
        self.waypoints = []
        self.current_waypoint_index = 0
        
    def reset(self):
        """Reset to start of path."""
        self.current_waypoint_index = 0
        self.predictor.reset()
        
    def update_position(self, x, y, yaw, timestamp=None):
        """
        Update current robot position.
        
        Args:
            x, y: Position in meters
            yaw: Heading in radians
            timestamp: Optional timestamp (uses time.time() if None)
        """
        if timestamp is None:
            timestamp = time.time()
            
        self.current_position = (x, y, yaw)
        self.predictor.update(x, y, yaw, timestamp)
        
    def get_current_target(self):
        """Get current target waypoint or None if complete."""
        if self.current_waypoint_index >= len(self.waypoints):
            return None
        return self.waypoints[self.current_waypoint_index]
    
    def get_progress(self):
        """Get progress through path (completed waypoints, total waypoints)."""
        return self.current_waypoint_index, len(self.waypoints)
    
    def is_complete(self):
        """Check if path following is complete."""
        return self.current_waypoint_index >= len(self.waypoints)
    
    def compute_command(self):
        """
        Compute movement command based on current position and target.
        
        Returns:
            (direction, turn_rate) tuple:
                - direction: 0 = turn in place, 1 = move forward
                - turn_rate: degrees/second (positive = right, negative = left)
                Note: This is inverted when sending to robot (robot expects positive = left)
            
            Returns (0, 0.0) if path is complete or no position update yet.
        """
        if self.current_position is None:
            return 0, 0.0
            
        if self.is_complete():
            return 0, 0.0
        
        target = self.get_current_target()
        if target is None:
            return 0, 0.0
        
        target_x, target_y = target
        robot_x, robot_y, robot_yaw = self.current_position
        
        # Apply prediction compensation if enabled
        if self.use_prediction:
            control_x, control_y, control_yaw = self.predictor.predict(
                robot_x, robot_y, robot_yaw,
                self.estimated_delay_ms / 1000.0
            )
        else:
            control_x, control_y, control_yaw = robot_x, robot_y, robot_yaw
        
        # Calculate distance to target
        dx = target_x - control_x
        dy = target_y - control_y
        distance = math.sqrt(dx**2 + dy**2)
        
        # Check if waypoint reached
        if distance < self.waypoint_tolerance:
            self.current_waypoint_index += 1
            # Recursively check next waypoint, but limit depth to avoid infinite loops
            if self.current_waypoint_index < len(self.waypoints):
                return self.compute_command()  # Immediately target next waypoint
            else:
                return 0, 0.0  # Path complete
        
        # Calculate desired heading
        desired_yaw = math.atan2(dy, dx)
        
        # Safety check for invalid angle
        if not math.isfinite(desired_yaw):
            return 0, 0.0
        
        # Calculate angle difference
        angle_diff = desired_yaw - control_yaw
        # Normalize to [-pi, pi]
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        angle_diff_deg = math.degrees(angle_diff)
        
        # Safety check for invalid angle difference
        if not math.isfinite(angle_diff_deg):
            return 0, 0.0
        
        # Determine direction and turn rate
        if abs(angle_diff_deg) > self.turn_in_place_threshold:
            # Turn in place
            direction = 0
            turn_rate = max(-self.max_turn_rate, 
                          min(self.max_turn_rate, angle_diff_deg * 2))
        else:
            # Move forward with turning
            direction = 1
            turn_rate = max(-self.max_turn_rate,
                          min(self.max_turn_rate, angle_diff_deg * self.proportional_gain))
        
        # Final safety check on turn rate
        if not math.isfinite(turn_rate):
            turn_rate = 0.0
        
        return direction, turn_rate
    
    def get_state(self):
        """
        Get current state for monitoring/debugging.
        
        Returns:
            dict with current state information
        """
        if self.current_position is None:
            return {
                'position': None,
                'target': None,
                'distance_to_target': None,
                'angle_to_target': None,
                'waypoint_index': self.current_waypoint_index,
                'total_waypoints': len(self.waypoints),
                'complete': self.is_complete()
            }
        
        target = self.get_current_target()
        if target is None:
            distance = None
            angle = None
        else:
            dx = target[0] - self.current_position[0]
            dy = target[1] - self.current_position[1]
            distance = math.sqrt(dx**2 + dy**2)
            desired_yaw = math.atan2(dy, dx)
            angle = desired_yaw - self.current_position[2]
            while angle > math.pi:
                angle -= 2 * math.pi
            while angle < -math.pi:
                angle += 2 * math.pi
        
        return {
            'position': self.current_position,
            'target': target,
            'distance_to_target': distance,
            'angle_to_target': angle,
            'waypoint_index': self.current_waypoint_index,
            'total_waypoints': len(self.waypoints),
            'complete': self.is_complete()
        }


class SimplePathFollower(PathFollower):
    """Simplified version without delay compensation for basic use cases."""
    
    def __init__(self, waypoints=None, **kwargs):
        kwargs['use_prediction'] = False
        kwargs['estimated_delay_ms'] = 0
        super().__init__(waypoints=waypoints, **kwargs)


def example_usage():
    """Example of how to use PathFollower in a control system."""
    
    # Define waypoints (x, y in meters)
    waypoints = [
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
        (0.0, 0.0)
    ]
    
    # Create follower
    follower = PathFollower(
        waypoints=waypoints,
        waypoint_tolerance=0.15,
        use_prediction=True,
        estimated_delay_ms=100
    )
    
    # Simulated control loop
    while not follower.is_complete():
        # Get robot position (from OptiTrack, encoders, etc.)
        robot_x, robot_y, robot_yaw = get_robot_position()  # Your function
        
        # Update follower with current position
        follower.update_position(robot_x, robot_y, robot_yaw)
        
        # Compute command
        direction, turn_rate = follower.compute_command()
        
        # Send to robot
        send_command(direction, turn_rate)  # Your function
        
        # Optional: Monitor state
        state = follower.get_state()
        print(f"Target {state['waypoint_index']}/{state['total_waypoints']}, "
              f"Distance: {state['distance_to_target']:.2f}m")
        
        time.sleep(0.1)  # 10Hz control loop
    
    # Stop robot when complete
    send_command(0, 0.0)
    print("Path complete!")


if __name__ == '__main__':
    print("PathFollower module - Import and use in your control system")
    print("See example_usage() for integration guide")

