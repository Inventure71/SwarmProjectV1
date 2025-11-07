#!/usr/bin/env python3
"""ROS-based robot command publisher for Hydra backend."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from typing import Dict, Optional

try:
    import rospy
    from geometry_msgs.msg import Twist, TwistStamped
except ImportError as exc:  # pragma: no cover - handled at runtime on Hydra
    rospy = None  # type: ignore
    Twist = None  # type: ignore
    TwistStamped = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@dataclass
class CommandLimits:
    max_linear: float
    max_angular: float


class ROSController:
    """Publish velocity commands to robot-specific cmd_vel topics."""

    def __init__(
        self,
        default_max_linear: float = 0.5,
        default_max_angular: float = 1.5,
        use_stamped: bool = False,
        frame_id: str = "base_link",
        queue_size: int = 10,
    ) -> None:
        if _IMPORT_ERROR is not None:
            raise ImportError(
                "rospy and geometry_msgs are required for ROSController"
            ) from _IMPORT_ERROR

        self._default_limits = CommandLimits(default_max_linear, default_max_angular)
        self._use_stamped = use_stamped
        self._frame_id = frame_id
        self._queue_size = queue_size

        self._publishers: Dict[str, rospy.Publisher] = {}
        self._limits: Dict[str, CommandLimits] = {}
        self._lock = threading.Lock()

    def register_robot(self, robot_name: str, robot_config: Dict) -> None:
        """Register (or update) a robot publisher based on configuration."""
        robot_type = robot_config.get("type", "real")
        if robot_type != "real":
            self.remove_robot(robot_name)
            return

        topic = robot_config.get("cmd_vel_topic")
        if not topic:
            topic = f"/{robot_name}/cmd_vel"

        # Coalesce None to defaults to avoid None arithmetic
        cfg_max_lin = robot_config.get("max_linear")
        cfg_max_ang = robot_config.get("max_angular")
        limits = CommandLimits(
            cfg_max_lin if isinstance(cfg_max_lin, (int, float)) else self._default_limits.max_linear,
            cfg_max_ang if isinstance(cfg_max_ang, (int, float)) else self._default_limits.max_angular,
        )

        with self._lock:
            if robot_name in self._publishers:
                self._publishers[robot_name].unregister()

            msg_type = TwistStamped if self._use_stamped else Twist
            publisher = rospy.Publisher(topic, msg_type, queue_size=self._queue_size)
            self._publishers[robot_name] = publisher
            self._limits[robot_name] = limits

        rospy.loginfo("[ROSController] Advertised %s on %s", robot_name, topic)

    def remove_robot(self, robot_name: str) -> None:
        with self._lock:
            publisher = self._publishers.pop(robot_name, None)
            self._limits.pop(robot_name, None)

        if publisher is not None:
            publisher.unregister()
            rospy.loginfo("[ROSController] Unregistered publisher for %s", robot_name)

    def shutdown(self) -> None:
        for name in list(self._publishers.keys()):
            self.remove_robot(name)

    def get_registered_robots(self) -> Dict[str, CommandLimits]:
        """Return a copy of registered robots and their limits."""
        with self._lock:
            return dict(self._limits)

    def send_command(
        self,
        robot_name: str,
        throttle: float,
        turn_rate_deg: float,
        max_linear: Optional[float] = None,
        max_angular: Optional[float] = None,
    ) -> bool:
        """Send command using throttle (-1..1) and turn rate in degrees per second."""
        limits = self._limits.get(robot_name, self._default_limits)
        linear_limit = max_linear if max_linear is not None else limits.max_linear
        angular_limit = max_angular if max_angular is not None else limits.max_angular

        throttle = max(-1.0, min(1.0, float(throttle)))
        angle_deg = float(turn_rate_deg)
        angle_rad = math.radians(angle_deg)

        linear_velocity = throttle * linear_limit
        angular_velocity = max(-angular_limit, min(angular_limit, angle_rad))

        return self.publish_twist(robot_name, linear_velocity, angular_velocity)

    def publish_twist(self, robot_name: str, linear_x: float, angular_z: float) -> bool:
        """Publish a Twist/TwistStamped command directly."""
        with self._lock:
            publisher = self._publishers.get(robot_name)

        if publisher is None:
            rospy.logwarn("[ROSController] No publisher for robot %s", robot_name)
            return False

        if self._use_stamped:
            msg = TwistStamped()
            msg.header.stamp = rospy.Time.now()
            msg.header.frame_id = self._frame_id
            msg.twist.linear.x = linear_x
            msg.twist.angular.z = angular_z
        else:
            msg = Twist()
            msg.linear.x = linear_x
            msg.angular.z = angular_z

        publisher.publish(msg)
        return True

