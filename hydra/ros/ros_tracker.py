#!/usr/bin/env python3
"""ROS-based robot pose tracker for Hydra backend."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, asdict
from typing import Dict, Optional

try:
    import rospy
    from geometry_msgs.msg import PoseStamped
except ImportError as exc:  # pragma: no cover - handled at runtime on Hydra
    rospy = None  # type: ignore
    PoseStamped = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@dataclass(frozen=True)
class PoseState:
    """Snapshot of a robot pose."""

    x: float
    y: float
    z: float
    yaw: float
    frame_id: str
    timestamp: float

    def as_dict(self) -> Dict[str, float]:
        """Return a dictionary representation (for JSON serialisation)."""
        return asdict(self)


def _quat_to_yaw(x: float, y: float, z: float, w: float) -> float:
    """Convert quaternion to yaw (Z rotation)."""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class ROSTracker:
    """Track robot poses by subscribing to ROS pose topics."""

    def __init__(self, queue_size: int = 10):
        if _IMPORT_ERROR is not None:
            raise ImportError(
                "rospy and geometry_msgs are required for ROSTracker"
            ) from _IMPORT_ERROR

        self._queue_size = queue_size
        self._lock = threading.Lock()
        self._poses: Dict[str, PoseState] = {}
        self._subscribers: Dict[str, rospy.Subscriber] = {}
        self._types: Dict[str, str] = {}

    def register_robot(self, robot_name: str, robot_config: Dict) -> None:
        """Register (or update) a robot subscription based on configuration."""
        robot_type = robot_config.get("type", "real")
        self._types[robot_name] = robot_type

        if robot_type != "real":
            self._unregister(robot_name)
            return

        self._unregister(robot_name)

        pose_topic = robot_config.get("pose_topic")
        if not pose_topic:
            umh_id = robot_config.get("umh_id")
            if not umh_id:
                raise ValueError(f"Robot '{robot_name}' missing 'umh_id' for tracking")
            pose_topic = f"/natnet_ros/{umh_id}/pose"

        callback = self._make_callback(robot_name)
        self._subscribers[robot_name] = rospy.Subscriber(
            pose_topic,
            PoseStamped,
            callback,
            queue_size=self._queue_size,
        )
        rospy.loginfo("[ROSTracker] Subscribed %s to %s", robot_name, pose_topic)

    def remove_robot(self, robot_name: str) -> None:
        """Remove a robot subscription and cached state."""
        self._unregister(robot_name)
        with self._lock:
            self._poses.pop(robot_name, None)
            self._types.pop(robot_name, None)

    def shutdown(self) -> None:
        """Unregister all subscribers."""
        for name in list(self._subscribers.keys()):
            self._unregister(name)
        with self._lock:
            self._poses.clear()

    def get_pose(self, robot_name: str) -> Optional[PoseState]:
        """Return the latest pose for a robot, if available."""
        with self._lock:
            return self._poses.get(robot_name)

    def get_all_poses(self) -> Dict[str, PoseState]:
        """Return a copy of all known poses."""
        with self._lock:
            return dict(self._poses)

    def _make_callback(self, robot_name: str):
        def _callback(msg: PoseStamped) -> None:
            position = msg.pose.position
            orientation = msg.pose.orientation
            yaw = _quat_to_yaw(orientation.x, orientation.y, orientation.z, orientation.w)

            pose = PoseState(
                x=position.x,
                y=position.y,
                z=position.z,
                yaw=yaw,
                frame_id=msg.header.frame_id or "world",
                timestamp=msg.header.stamp.to_sec() if msg.header.stamp else rospy.Time.now().to_sec(),
            )

            with self._lock:
                self._poses[robot_name] = pose

        return _callback

    def _unregister(self, robot_name: str) -> None:
        subscriber = self._subscribers.pop(robot_name, None)
        if subscriber is not None:
            subscriber.unregister()
            rospy.loginfo("[ROSTracker] Unsubscribed %s", robot_name)

