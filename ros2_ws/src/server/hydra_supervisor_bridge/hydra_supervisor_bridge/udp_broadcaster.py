from __future__ import annotations

import json
import socket
from typing import List


class UDPBroadcaster:
    def __init__(self, client_ips: List[str]) -> None:
        self.client_ips = client_ips
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_robot_state(self, client_port: int, message) -> None:
        if client_port <= 0:
            return
        data = json.dumps(message).encode("utf-8")
        for client_ip in self.client_ips:
            try:
                self._socket.sendto(data, (client_ip, client_port))
            except OSError:
                continue

    def close(self) -> None:
        self._socket.close()
