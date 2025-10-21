#!/usr/bin/env python3
"""
Simple demonstration of path following without UI.
Shows the core functionality of the PathFollower module.
"""

import time
import math
from path_follower import PathFollower


class SimulatedRobot:
    """Simple simulated robot for demonstration."""
    
    def __init__(self, x=0.0, y=0.0, yaw=0.0):
        self.x = x
        self.y = y
        self.yaw = yaw
        self.max_speed = 0.5  # m/s
        self.max_turn_rate = 1.5  # rad/s
        
    def update(self, direction, turn_rate_deg, dt):
        """Update robot based on command."""
        turn_rate_rad = turn_rate_deg * math.pi / 180.0
        turn_rate_rad = max(-self.max_turn_rate, min(self.max_turn_rate, turn_rate_rad))
        
        # Update heading
        self.yaw += turn_rate_rad * dt
        
        # Normalize yaw
        while self.yaw > math.pi:
            self.yaw -= 2 * math.pi
        while self.yaw < -math.pi:
            self.yaw += 2 * math.pi
        
        # Update position if moving forward
        if direction == 1:
            self.x += self.max_speed * math.cos(self.yaw) * dt
            self.y += self.max_speed * math.sin(self.yaw) * dt
    
    def get_position(self):
        """Get current position."""
        return self.x, self.y, self.yaw


def main():
    """Demonstrate path following."""
    
    print("=" * 60)
    print("Path Following Demonstration")
    print("=" * 60)
    
    # Define a square path
    waypoints = [
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
        (0.0, 0.0)
    ]
    
    print(f"\nPath: {len(waypoints)} waypoints")
    for i, (x, y) in enumerate(waypoints, 1):
        print(f"  {i}. ({x:.1f}m, {y:.1f}m)")
    
    # Create robot starting at origin
    robot = SimulatedRobot(x=0.0, y=0.0, yaw=0.0)
    print(f"\nRobot starting at ({robot.x:.2f}m, {robot.y:.2f}m)")
    
    # Create path follower
    follower = PathFollower(
        waypoints=waypoints,
        waypoint_tolerance=0.10,
        use_prediction=False  # Disabled for simple demo
    )
    
    print("\nStarting path following...")
    print("-" * 60)
    
    dt = 0.1  # 10Hz control loop
    step = 0
    
    try:
        while not follower.is_complete():
            # Get robot position
            x, y, yaw = robot.get_position()
            
            # Update follower
            follower.update_position(x, y, yaw)
            
            # Compute command
            direction, turn_rate = follower.compute_command()
            
            # Update robot
            robot.update(direction, turn_rate, dt)
            
            # Print status every 10 steps (1 second)
            if step % 10 == 0:
                state = follower.get_state()
                yaw_deg = math.degrees(yaw)
                
                print(f"[{step*dt:5.1f}s] Pos: ({x:5.2f}, {y:5.2f}) | "
                      f"Heading: {yaw_deg:6.1f}° | "
                      f"Target: {state['waypoint_index']+1}/{state['total_waypoints']}", end="")
                
                if state['distance_to_target'] is not None:
                    print(f" | Dist: {state['distance_to_target']:5.2f}m", end="")
                
                if direction == 0:
                    print(" | [TURNING]", end="")
                else:
                    print(" | [FORWARD]", end="")
                
                print()
            
            step += 1
            time.sleep(dt)
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    print("-" * 60)
    print(f"\nPath complete! Total time: {step*dt:.1f}s")
    print(f"Final position: ({robot.x:.2f}m, {robot.y:.2f}m)")
    print(f"Distance traveled: ~{calculate_distance_traveled(waypoints):.2f}m")
    print("\n" + "=" * 60)


def calculate_distance_traveled(waypoints):
    """Calculate approximate path length."""
    total = 0.0
    prev = (0.0, 0.0)
    for wp in waypoints:
        dx = wp[0] - prev[0]
        dy = wp[1] - prev[1]
        total += math.sqrt(dx*dx + dy*dy)
        prev = wp
    return total


if __name__ == '__main__':
    main()

