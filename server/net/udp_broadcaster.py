#!/usr/bin/env python3
"""UDP broadcaster for sending robot state to pre-configured clients without waiting for connections."""

from __future__ import annotations

import json
import socket
from typing import Dict, List, Tuple

JsonDict = Dict[str, object]


class UDPBroadcaster:
    """
    Sends UDP messages to pre-configured client IPs without requiring connection handshake.
    Each robot's data is sent to its specific client_port.
    """

    def __init__(self, client_ips: List[str]) -> None:
        """
        Initialize broadcaster with list of client IPs.
        
        Args:
            client_ips: List of IP addresses to broadcast to
        """
        self.client_ips = client_ips
        self._socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Enable broadcast if needed (for subnet broadcasts)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        print(f"[UDPBroadcaster] Initialized with {len(client_ips)} client IPs: {client_ips}")

    def send_robot_state(self, robot_name: str, client_port: int, message: JsonDict) -> None:
        """
        Send a message to all configured clients on the robot's specific port.
        
        Args:
            robot_name: Name of the robot (for logging)
            client_port: Port specific to this robot
            message: JSON message to send
        """
        if client_port <= 0:
            # Skip invalid ports (dummy robots)
            return
            
        data = json.dumps(message).encode("utf-8")
        
        for client_ip in self.client_ips:
            addr = (client_ip, client_port)
            try:
                self._socket.sendto(data, addr)
            except OSError as exc:
                # Log but don't fail - client may not be available
                print(f"[UDPBroadcaster] Failed to send {robot_name} state to {addr}: {exc}")

    def broadcast_to_all_clients(self, port: int, message: JsonDict) -> None:
        """
        Broadcast a message to all clients on a specific port.
        Useful for connection status or global state messages.
        
        Args:
            port: Port to send to on all clients
            message: JSON message to send
        """
        if port <= 0:
            return
            
        data = json.dumps(message).encode("utf-8")
        
        for client_ip in self.client_ips:
            addr = (client_ip, port)
            try:
                self._socket.sendto(data, addr)
            except OSError as exc:
                print(f"[UDPBroadcaster] Failed to broadcast to {addr}: {exc}")

    def close(self) -> None:
        """Close the UDP socket."""
        if self._socket:
            self._socket.close()

