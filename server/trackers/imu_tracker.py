#!/usr/bin/env python3
"""IMU tracker for robots."""

from __future__ import annotations

from typing import Dict, Optional

try:
    import rospy
    from sensor_msgs.msg import Imu
except ImportError as exc:
    rospy = None
    Imu = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .base_tracker import BaseTracker


class IMUTracker(BaseTracker):
    """Track IMU data for robots."""
    
    def __init__(self, queue_size: int = 10):
        """Initialize IMU tracker."""
        if _IMPORT_ERROR is not None:
            raise ImportError(
                "rospy and sensor_msgs are required for IMUTracker"
            ) from _IMPORT_ERROR
        
        super().__init__(queue_size)
    
    def _get_topic_from_config(self, robot_config: Dict) -> Optional[str]:
        """Get IMU topic from config or construct default."""
        imu_topic = robot_config.get("imu_topic")
        if imu_topic:
            return imu_topic
        
        robot_name = robot_config.get("name")
        if robot_name:
            return f"/{robot_name}/imu"
        
        return None
    
    def _get_message_type(self):
        """Return Imu message type."""
        return Imu
    
    def _process_message(self, robot_name: str, msg: Imu) -> None:
        """Process IMU message and update robot."""
        with self._lock:
            robot = self._robots.get(robot_name)
        
        if robot is None:
            return
        
        robot.update_imu(
            linear_accel=(msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z),
            angular_velocity=(msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z),
            orientation=(msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w),
        )
