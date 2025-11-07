#!/usr/bin/env python3
"""
Backend Controller Proxy
Handles communication with the backend server.
"""

from typing import Optional


class BackendControllerProxy:
    """Proxy that forwards control commands to the backend via UDP."""

    def __init__(self, udp_client):
        self._udp_client = udp_client
        self._default_robot: Optional[str] = None

    @property
    def connected(self) -> bool:
        """Check if connected to backend."""
        status = self._udp_client.get_connection_status()
        if not status:
            return False
        return bool(status.get("ros_connected", False))

    def set_default_robot(self, robot_name: str) -> None:
        """Set the default robot for commands."""
        self._default_robot = robot_name

    def send_command(self, throttle: float, angle: float, robot_name: Optional[str] = None) -> bool:
        """Send manual control command to a robot."""
        target = robot_name or self._default_robot
        if not target:
            return False
        payload = {
            "type": "manual_control",
            "data": {
                "robot": target,
                "throttle": float(throttle),
                "turn_rate": float(angle),
            },
        }
        self._udp_client.send(payload)
        return True


class RobotStateProxy:
    """Minimal robot facade for UI services relying on position queries."""

    def __init__(self, app, name: str, robot_type: str):
        self._app = app
        self.username = name
        self.robot_type = robot_type

    def get_position(self):
        """Get robot position from app state."""
        return self._app.state.get_robot_position(self.username)

    def set_location(self, x: float, y: float, yaw: float = 0.0) -> None:
        """Set robot position in app state."""
        self._app.state.set_robot_position(self.username, x, y, yaw)

