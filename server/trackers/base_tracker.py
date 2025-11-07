#!/usr/bin/env python3
"""Base tracker class for robot data subscription."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any

try:
    import rospy
except ImportError as exc:  # pragma: no cover
    rospy = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class BaseTracker(ABC):
    """
    Abstract base class for robot data trackers.
    
    Each tracker subscribes to specific ROS topics and updates
    corresponding properties in Robot instances.
    
    Design principles:
    - Single Responsibility: Each tracker handles one type of data
    - Thread-safe: All operations use locks for concurrent access
    - Plug-and-Play: Easy to add new trackers without modifying existing code
    """
    
    def __init__(self, queue_size: int = 10):
        """
        Initialize base tracker.
        
        Args:
            queue_size: ROS subscriber queue size
        """
        if _IMPORT_ERROR is not None:
            raise ImportError(
                "rospy is required for trackers"
            ) from _IMPORT_ERROR
        
        self._queue_size = queue_size
        self._lock = threading.Lock()
        self._subscribers: Dict[str, rospy.Subscriber] = {}
        self._robots: Dict[str, Any] = {}  # Maps robot_name -> Robot instance
        self._callback_counts: Dict[str, int] = {}
    
    def register_robot(self, robot_name: str, robot_instance: Any, robot_config: Dict) -> None:
        """
        Register a robot for tracking.
        
        Args:
            robot_name: Name/identifier of the robot
            robot_instance: Reference to the Robot instance to update
            robot_config: Configuration dictionary for the robot
        """
        robot_type = robot_config.get("type", "real")
        
        # Only track real robots (dummy robots don't have ROS topics)
        if robot_type != "real":
            self.remove_robot(robot_name)
            return
        
        # Store robot reference
        with self._lock:
            self._robots[robot_name] = robot_instance
        
        # Unregister existing subscriber if any
        self._unregister_subscriber(robot_name)
        
        # Get topic from config or construct default
        topic = self._get_topic_from_config(robot_config)
        if not topic:
            rospy.logwarn(
                "[%s] No topic configured for %s, skipping",
                self.__class__.__name__, robot_name
            )
            return
        
        # Create callback and subscribe
        callback = self._make_callback(robot_name)
        msg_type = self._get_message_type()
        
        self._subscribers[robot_name] = rospy.Subscriber(
            topic,
            msg_type,
            callback,
            queue_size=self._queue_size,
        )
        
        rospy.loginfo(
            "[%s] Subscribed %s to %s",
            self.__class__.__name__, robot_name, topic
        )
        
        # Check if topic exists
        self._check_topic_exists(topic, robot_name)
    
    def remove_robot(self, robot_name: str) -> None:
        """Remove a robot from tracking."""
        self._unregister_subscriber(robot_name)
        with self._lock:
            self._robots.pop(robot_name, None)
            self._callback_counts.pop(robot_name, None)
    
    def shutdown(self) -> None:
        """Shutdown all subscribers."""
        for name in list(self._subscribers.keys()):
            self._unregister_subscriber(name)
        with self._lock:
            self._robots.clear()
            self._callback_counts.clear()
    
    def get_tracked_robots(self) -> list:
        """Get list of currently tracked robot names."""
        with self._lock:
            return list(self._robots.keys())
    
    @abstractmethod
    def _get_topic_from_config(self, robot_config: Dict) -> Optional[str]:
        """
        Extract or construct the ROS topic from robot configuration.
        
        Args:
            robot_config: Robot configuration dictionary
            
        Returns:
            ROS topic string or None if not available
        """
        pass
    
    @abstractmethod
    def _get_message_type(self):
        """
        Get the ROS message type for this tracker.
        
        Returns:
            ROS message class (e.g., sensor_msgs.msg.BatteryState)
        """
        pass
    
    @abstractmethod
    def _process_message(self, robot_name: str, msg) -> None:
        """
        Process incoming ROS message and update robot instance.
        
        Args:
            robot_name: Name of the robot
            msg: ROS message
        """
        pass
    
    def _make_callback(self, robot_name: str):
        """Create ROS callback for a specific robot."""
        def _callback(msg) -> None:
            # Update callback count
            with self._lock:
                self._callback_counts[robot_name] = self._callback_counts.get(robot_name, 0) + 1
                count = self._callback_counts[robot_name]
            
            # Process the message
            try:
                self._process_message(robot_name, msg)
            except Exception as e:
                rospy.logerr(
                    "[%s] Error processing message for %s: %s",
                    self.__class__.__name__, robot_name, e
                )
            
            # Log first message and periodically
            if count == 1:
                rospy.loginfo(
                    "[%s] First message received for %s",
                    self.__class__.__name__, robot_name
                )
            elif count % 100 == 0:
                rospy.logdebug(
                    "[%s] Message #%d for %s",
                    self.__class__.__name__, count, robot_name
                )
        
        return _callback
    
    def _unregister_subscriber(self, robot_name: str) -> None:
        """Unregister subscriber for a robot."""
        subscriber = self._subscribers.pop(robot_name, None)
        if subscriber is not None:
            subscriber.unregister()
            rospy.loginfo(
                "[%s] Unsubscribed %s",
                self.__class__.__name__, robot_name
            )
    
    def _check_topic_exists(self, topic: str, robot_name: str) -> None:
        """Check if topic exists and log warning if not."""
        try:
            published_topics = rospy.get_published_topics()
            topic_names = [t[0] for t in published_topics]
            if topic not in topic_names:
                rospy.logwarn(
                    "[%s] Topic %s not currently publishing for %s. "
                    "Tracker will wait for topic to become available.",
                    self.__class__.__name__, topic, robot_name
                )
        except Exception as e:
            rospy.logwarn(
                "[%s] Could not check if topic exists: %s",
                self.__class__.__name__, e
            )

