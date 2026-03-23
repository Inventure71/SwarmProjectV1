#!/usr/bin/env python3
"""
Command Sender
Handles sending commands to the supervisor bridge.
"""

from typing import List, Tuple


class CommandSender:
    """Sends commands to the supervisor bridge."""
    
    def __init__(self, udp_client):
        self.udp_client = udp_client
    
    def push_path_to_backend(self, robot_name: str, waypoints: List[Tuple[float, float]]) -> None:
        """Send path waypoints to the supervisor bridge."""
        payload = {
            "type": "set_path",
            "data": {
                "robot": robot_name,
                "waypoints": [list(point) for point in waypoints],
            },
        }
        self.udp_client.send(payload)
    
    def send_racing_config(self, robot_name: str, racing_config) -> None:
        """Send racing configuration to the supervisor bridge."""
        payload = {
            "type": "set_racing_config",
            "data": {
                "robot": robot_name,
                "offset": racing_config.lateral_offset,
                "speed": racing_config.speed_multiplier,
                "loop": racing_config.loop_path,
            },
        }
        self.udp_client.send(payload)
    
    def start_path(self, robot_name: str) -> None:
        """Start path following for a robot."""
        self.udp_client.send({"type": "start_path", "data": {"robot": robot_name}})
    
    def stop_path(self, robot_name: str) -> None:
        """Stop path following for a robot."""
        self.udp_client.send({"type": "stop_path", "data": {"robot": robot_name}})
    
    def clear_path(self, robot_name: str) -> None:
        """Clear path for a robot."""
        self.udp_client.send({"type": "clear_path", "data": {"robot": robot_name}})
    
    def start_all_paths(self) -> None:
        """Start path following for all robots."""
        self.udp_client.send({"type": "start_all_paths", "data": {}})
    
    def stop_all(self) -> None:
        """Stop all robots."""
        self.udp_client.send({"type": "stop_all", "data": {}})
    
    def emergency_stop(self) -> None:
        """Emergency stop all robots."""
        self.udp_client.send({"type": "emergency_stop", "data": {}})
    
    def sync_parameters(self, params: dict) -> None:
        """Sync control parameters with the supervisor bridge."""
        payload = {"type": "set_parameters", "data": params}
        self.udp_client.send(payload)
    
    def add_robot(self, robot_config: dict) -> None:
        """Add a new robot."""
        payload = {"type": "add_robot", "data": robot_config}
        self.udp_client.send(payload)
