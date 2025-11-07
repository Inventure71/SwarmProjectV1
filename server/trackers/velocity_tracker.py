#!/usr/bin/env python3
"""Velocity tracker for robots."""

from __future__ import annotations

from typing import Dict, Optional

try:
    import rospy
    from geometry_msgs.msg import TwistStamped, Twist
except ImportError as exc:
    rospy = None
    TwistStamped = None
    Twist = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .base_tracker import BaseTracker


class VelocityTracker(BaseTracker):
    """Track velocity data for robots."""
    
    def __init__(self, queue_size: int = 10):
        """Initialize velocity tracker."""
        if _IMPORT_ERROR is not None:
            raise ImportError(
                "rospy and geometry_msgs are required for VelocityTracker"
            ) from _IMPORT_ERROR
        
        super().__init__(queue_size)
    
    def _get_topic_from_config(self, robot_config: Dict) -> Optional[str]:
        """Get velocity topic from config or construct default."""
        velocity_topic = robot_config.get("velocity_topic")
        if velocity_topic:
            return velocity_topic
        
        robot_name = robot_config.get("name")
        if robot_name:
            return f"/{robot_name}/velocity"
        
        return None
    
    def _get_message_type(self):
        """Return Twist or TwistStamped message type."""
        return TwistStamped
    
    def _process_message(self, robot_name: str, msg) -> None:
        """Process velocity message and update robot."""
        with self._lock:
            robot = self._robots.get(robot_name)
        
        if robot is None:
            return
        
        if isinstance(msg, TwistStamped):
            twist = msg.twist
        else:
            twist = msg
        
        robot.update_velocity(
            linear_x=twist.linear.x,
            linear_y=twist.linear.y,
            angular_z=twist.angular.z,
        )

