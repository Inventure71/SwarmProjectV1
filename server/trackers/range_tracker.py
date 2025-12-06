#!/usr/bin/env python3
"""Range sensors tracker for robots."""

from __future__ import annotations

from typing import Dict, Optional, Any

try:
    import rospy
    from sensor_msgs.msg import Range
except ImportError as exc:
    rospy = None
    Range = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .base_tracker import BaseTracker


class RangeSensorsTracker(BaseTracker):
    """Track range sensor data for robots (front-left, front-right, rear-left, rear-right)."""
    
    def __init__(self, queue_size: int = 10):
        """Initialize range sensors tracker."""
        if _IMPORT_ERROR is not None:
            raise ImportError(
                "rospy and sensor_msgs are required for RangeSensorsTracker"
            ) from _IMPORT_ERROR
        
        super().__init__(queue_size)
        self._range_data: Dict[str, Dict[str, float]] = {}
    
    def _get_topic_from_config(self, robot_config: Dict) -> Optional[str]:
        """Get range topic from config - tracks all 4 sensors."""
        robot_name = robot_config.get("name")
        if not robot_name:
            return None
        
        # We'll subscribe to all 4 range topics separately
        return None
    
    def register_robot(self, robot_name: str, robot_instance: Any, robot_config: Dict) -> None:
        """Register robot and subscribe to all 4 range sensors."""
        robot_type = robot_config.get("type", "real")
        
        if robot_type != "real":
            self.remove_robot(robot_name)
            return
        
        with self._lock:
            self._robots[robot_name] = robot_instance
            self._range_data[robot_name] = {}
        
        robot_name_config = robot_config.get("name")
        if not robot_name_config:
            return
        
        # Subscribe to all 4 range sensors
        sensors = ["fl", "fr", "rl", "rr"]
        for sensor in sensors:
            topic = f"/{robot_name_config}/range/{sensor}"
            callback = self._make_callback(robot_name, sensor)
            subscriber = rospy.Subscriber(
                topic,
                Range,
                callback,
                queue_size=self._queue_size,
            )
            key = f"{robot_name}_{sensor}"
            self._subscribers[key] = subscriber
            rospy.loginfo("[RangeSensorsTracker] Subscribed %s to %s", robot_name, topic)
    
    def _get_message_type(self):
        """Return Range message type."""
        return Range
    
    def _make_callback(self, robot_name: str, sensor: str):
        """Create callback for a specific sensor."""
        def _callback(msg: Range) -> None:
            with self._lock:
                robot = self._robots.get(robot_name)
                if robot:
                    self._range_data[robot_name][sensor] = msg.range
                    robot.update_range_sensors(self._range_data[robot_name].copy())
        return _callback
    
    def _process_message(self, robot_name: str, msg) -> None:
        """Not used - handled by individual callbacks."""
        pass
    
    def remove_robot(self, robot_name: str) -> None:
        """Remove robot and all its sensor subscriptions."""
        sensors = ["fl", "fr", "rl", "rr"]
        for sensor in sensors:
            key = f"{robot_name}_{sensor}"
            subscriber = self._subscribers.pop(key, None)
            if subscriber:
                subscriber.unregister()
        
        with self._lock:
            self._robots.pop(robot_name, None)
            self._range_data.pop(robot_name, None)

