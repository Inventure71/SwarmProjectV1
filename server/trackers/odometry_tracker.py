#!/usr/bin/env python3
"""Odometry tracker for robots."""

from __future__ import annotations

from typing import Dict, Optional

try:
    import rospy
    from nav_msgs.msg import Odometry
except ImportError as exc:
    rospy = None
    Odometry = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .base_tracker import BaseTracker


class OdometryTracker(BaseTracker):
    """Track odometry data for robots."""
    
    def __init__(self, queue_size: int = 10):
        """Initialize odometry tracker."""
        if _IMPORT_ERROR is not None:
            raise ImportError(
                "rospy and nav_msgs are required for OdometryTracker"
            ) from _IMPORT_ERROR
        
        super().__init__(queue_size)
    
    def _get_topic_from_config(self, robot_config: Dict) -> Optional[str]:
        """Get odometry topic from config or construct default."""
        odom_topic = robot_config.get("odom_topic")
        if odom_topic:
            return odom_topic
        
        robot_name = robot_config.get("name")
        if robot_name:
            return f"/{robot_name}/odom"
        
        return None
    
    def _get_message_type(self):
        """Return Odometry message type."""
        return Odometry
    
    def _process_message(self, robot_name: str, msg: Odometry) -> None:
        """Process odometry message and update robot."""
        with self._lock:
            robot = self._robots.get(robot_name)
        
        if robot is None:
            return
        
        pos = msg.pose.pose.position
        ori = msg.pose.pose.orientation
        vel = msg.twist.twist
        
        robot.update_odometry(
            position=(pos.x, pos.y, pos.z),
            orientation=(ori.x, ori.y, ori.z, ori.w),
            linear_velocity=(vel.linear.x, vel.linear.y, vel.linear.z),
            angular_velocity=(vel.angular.x, vel.angular.y, vel.angular.z),
        )

