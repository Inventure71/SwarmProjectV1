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
        
        throttle, turn_rate = follower.compute_command()
        send_command_to_robot(throttle, turn_rate)
        
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
                 estimated_delay_ms=100,
                 curvature_speed_gain=1.2,
                 min_speed_ratio=0.05,
                 slow_down_distance=0.5,
                 path_simplification_tolerance=0.05,
                 min_waypoint_separation=0.12,
                 segment_pass_distance=0.08,
                 segment_pass_lateral_factor=1.5,
                 waypoint_approach_slowdown=0.4,
                 corner_keep_angle_deg=20.0):
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
            curvature_speed_gain: Gain applied when reducing speed for tighter turns
            min_speed_ratio: Minimum throttle to apply while moving forward
            slow_down_distance: Distance from final waypoint to start slowing down (meters)
        """
        self.path_simplification_tolerance = max(0.0, path_simplification_tolerance)
        self.min_waypoint_separation = max(0.0, min_waypoint_separation)
        self.segment_pass_distance = max(0.0, segment_pass_distance)
        self.segment_pass_lateral_factor = max(1.0, segment_pass_lateral_factor)
        self.waypoint_approach_slowdown = max(0.0, waypoint_approach_slowdown)
        self.corner_keep_angle_rad = math.radians(max(0.0, corner_keep_angle_deg))

        self.raw_waypoints = list(waypoints) if waypoints is not None else []
        self.waypoints = self._process_waypoints(self.raw_waypoints)
        self.waypoint_tolerance = waypoint_tolerance
        self.turn_in_place_threshold = turn_in_place_threshold
        self.proportional_gain = proportional_gain
        self.max_turn_rate = max_turn_rate
        self.use_prediction = use_prediction
        self.estimated_delay_ms = estimated_delay_ms
        self.curvature_speed_gain = curvature_speed_gain
        self.min_speed_ratio = min_speed_ratio
        self.slow_down_distance = slow_down_distance
        self.soft_turn_stop_ratio = 0.6
        self.soft_turn_stop_distance = max(0.3, self.waypoint_tolerance * 2.0)
        
        self.current_waypoint_index = 0
        self.current_position = None
        self.predictor = PositionPredictor()
        
    def set_waypoints(self, waypoints):
        """Set new waypoints and reset to beginning."""
        self.raw_waypoints = list(waypoints)
        self.waypoints = self._process_waypoints(self.raw_waypoints)
        self.current_waypoint_index = 0
        self.predictor.reset()  # Reset predictor when setting new waypoints
        
    def add_waypoint(self, x, y):
        """Add a waypoint to the path."""
        self.raw_waypoints.append((x, y))
        self.waypoints = self._process_waypoints(self.raw_waypoints)
        if self.waypoints:
            self.current_waypoint_index = min(self.current_waypoint_index, len(self.waypoints) - 1)

    def clear_waypoints(self):
        """Clear all waypoints."""
        self.raw_waypoints = []
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
            (throttle, turn_rate) tuple:
                - throttle: forward command ratio in [0, 1]
                - turn_rate: degrees/second (positive = right, negative = left)
                Note: This is inverted when sending to robot (robot expects positive = left)
            
            Returns (0.0, 0.0) if path is complete or no position update yet.
        """
        if self.current_position is None:
            return 0.0, 0.0
            
        if self.is_complete():
            return 0.0, 0.0
        
        target = self.get_current_target()
        if target is None:
            return 0.0, 0.0
        
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

        # Check if waypoint reached or safely passed
        if self._should_advance_waypoint(distance, control_x, control_y, robot_x, robot_y):
            self.current_waypoint_index += 1
            # Recursively check next waypoint, but limit depth to avoid infinite loops
            if self.current_waypoint_index < len(self.waypoints):
                return self.compute_command()  # Immediately target next waypoint
            else:
                return 0.0, 0.0  # Path complete
        
        # Calculate desired heading
        desired_yaw = math.atan2(dy, dx)
        
        # Safety check for invalid angle
        if not math.isfinite(desired_yaw):
            return 0.0, 0.0
        
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
            return 0.0, 0.0
        
        # Determine throttle and turn rate
        if abs(angle_diff_deg) > self.turn_in_place_threshold:
            # Turn in place
            throttle = 0.0
            turn_rate = max(-self.max_turn_rate, 
                          min(self.max_turn_rate, angle_diff_deg * 2))
        else:
            # Move forward with turning
            turn_rate = max(-self.max_turn_rate,
                          min(self.max_turn_rate, angle_diff_deg * self.proportional_gain))
            turn_ratio = abs(turn_rate) / self.max_turn_rate if self.max_turn_rate > 0 else 0.0
            curvature_scale = 1.0 / (1.0 + self.curvature_speed_gain * turn_ratio)
            if curvature_scale <= self.min_speed_ratio:
                throttle = 0.0
            else:
                throttle = max(self.min_speed_ratio, min(1.0, curvature_scale))
            
            # Apply distance-based throttle reduction near final waypoint
            if self.current_waypoint_index + 1 >= len(self.waypoints) and self.slow_down_distance > 1e-6 and distance < self.slow_down_distance:
                distance_scale = self.min_speed_ratio + \
                                 (1.0 - self.min_speed_ratio) * \
                                 (distance / self.slow_down_distance)
                distance_scale = max(0.0, min(1.0, distance_scale))
                throttle = min(throttle, distance_scale)
                if throttle < self.min_speed_ratio:
                    throttle = 0.0
            
            if throttle > 0.0:
                high_angle = abs(angle_diff_deg) > self.turn_in_place_threshold * self.soft_turn_stop_ratio
                if high_angle and distance < self.soft_turn_stop_distance:
                    throttle = 0.0

            if throttle > 0.0 and self.waypoint_approach_slowdown > 1e-6:
                if distance < self.waypoint_approach_slowdown:
                    distance_scale = max(0.0, min(1.0, distance / self.waypoint_approach_slowdown))
                    throttle = min(throttle, distance_scale)
                if distance < self.waypoint_tolerance * 2.0:
                    denom = max(self.waypoint_tolerance * 2.0, 1e-6)
                    close_scale = distance / denom
                    throttle = min(throttle, close_scale)
        
        # Final safety check on turn rate
        if not math.isfinite(turn_rate):
            turn_rate = 0.0
        
        # Clamp throttle
        if not math.isfinite(throttle):
            throttle = 0.0
        throttle = max(0.0, min(1.0, throttle))
        
        return throttle, turn_rate

    def _process_waypoints(self, waypoints):
        """Simplify and space waypoints for smoother tracking."""
        if not waypoints:
            return []

        processed = list(waypoints)

        if self.path_simplification_tolerance > 1e-6 and len(processed) > 2:
            processed = self._simplify_rdp(processed, self.path_simplification_tolerance)

        if self.min_waypoint_separation > 1e-6 and len(processed) > 1:
            processed = self._enforce_min_spacing(processed, self.min_waypoint_separation)

        return processed

    def _simplify_rdp(self, points, epsilon):
        """Ramer-Douglas-Peucker simplification."""
        if len(points) < 3:
            return list(points)

        start = points[0]
        end = points[-1]
        index = -1
        max_distance = 0.0

        for i in range(1, len(points) - 1):
            distance = self._point_to_segment_distance(points[i], start, end)
            if distance > max_distance:
                max_distance = distance
                index = i

        if max_distance > epsilon:
            left = self._simplify_rdp(points[: index + 1], epsilon)
            right = self._simplify_rdp(points[index:], epsilon)
            return left[:-1] + right

        return [start, end]

    def _enforce_min_spacing(self, points, min_distance):
        """Ensure minimum spacing while preserving sharp corners."""
        if len(points) <= 2:
            return list(points)

        filtered = [points[0]]
        for i in range(1, len(points) - 1):
            candidate = points[i]
            last_kept = filtered[-1]
            dist_last = math.hypot(candidate[0] - last_kept[0], candidate[1] - last_kept[1])

            if dist_last >= min_distance:
                filtered.append(candidate)
                continue

            next_point = points[i + 1]
            v1 = (candidate[0] - last_kept[0], candidate[1] - last_kept[1])
            v2 = (next_point[0] - candidate[0], next_point[1] - candidate[1])
            angle = self._angle_between(v1, v2)

            if angle >= self.corner_keep_angle_rad:
                filtered.append(candidate)

        filtered.append(points[-1])
        return filtered

    def _point_to_segment_distance(self, point, start, end):
        """Compute perpendicular distance from point to segment."""
        sx, sy = start
        ex, ey = end
        px, py = point
        seg_dx = ex - sx
        seg_dy = ey - sy
        seg_len_sq = seg_dx ** 2 + seg_dy ** 2

        if seg_len_sq < 1e-9:
            return math.hypot(px - sx, py - sy)

        t = ((px - sx) * seg_dx + (py - sy) * seg_dy) / seg_len_sq
        t = max(0.0, min(1.0, t))
        proj_x = sx + t * seg_dx
        proj_y = sy + t * seg_dy
        return math.hypot(px - proj_x, py - proj_y)

    def _angle_between(self, vec_a, vec_b):
        """Compute angle between two vectors."""
        ax, ay = vec_a
        bx, by = vec_b
        norm_a = math.hypot(ax, ay)
        norm_b = math.hypot(bx, by)
        if norm_a < 1e-9 or norm_b < 1e-9:
            return 0.0
        dot = ax * bx + ay * by
        cos_angle = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
        return math.acos(cos_angle)

    def _should_advance_waypoint(self, distance, control_x, control_y, robot_x, robot_y):
        """Decide if current waypoint can be considered reached or safely passed."""
        if distance < self.waypoint_tolerance:
            return True

        idx = self.current_waypoint_index
        if idx + 1 >= len(self.waypoints):
            return False

        target = self.waypoints[idx]
        next_target = self.waypoints[idx + 1]

        seg_dx = next_target[0] - target[0]
        seg_dy = next_target[1] - target[1]
        seg_len = math.hypot(seg_dx, seg_dy)

        if seg_len < 1e-6:
            return True

        vector_to_robot = (robot_x - target[0], robot_y - target[1])
        parallel = (vector_to_robot[0] * seg_dx + vector_to_robot[1] * seg_dy) / seg_len

        if parallel < 0.0:
            return False

        lateral = abs(vector_to_robot[0] * seg_dy - vector_to_robot[1] * seg_dx) / seg_len
        lateral_limit = self.waypoint_tolerance * self.segment_pass_lateral_factor

        if lateral > lateral_limit:
            return False

        if seg_len <= max(self.min_waypoint_separation * 0.5, self.segment_pass_distance * 0.75):
            return True

        pass_margin = max(self.segment_pass_distance, seg_len * 0.1)
        pass_threshold = seg_len - pass_margin

        if parallel >= pass_threshold:
            return True

        if parallel >= seg_len and lateral <= lateral_limit * 0.8:
            return True

        return False
    
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
        throttle, turn_rate = follower.compute_command()
        
        # Send to robot
        send_command(throttle, turn_rate)  # Your function
        
        # Optional: Monitor state
        state = follower.get_state()
        print(f"Target {state['waypoint_index']}/{state['total_waypoints']}, "
              f"Distance: {state['distance_to_target']:.2f}m")
        
        time.sleep(0.1)  # 10Hz control loop
    
    # Stop robot when complete
    send_command(0.0, 0.0)
    print("Path complete!")


if __name__ == '__main__':
    print("PathFollower module - Import and use in your control system")
    print("See example_usage() for integration guide")
