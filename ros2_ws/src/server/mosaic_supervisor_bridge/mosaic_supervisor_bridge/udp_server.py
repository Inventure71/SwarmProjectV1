from __future__ import annotations

import json
import socket
import threading
import time
from typing import Callable, Dict, Optional, Tuple


JsonDict = Dict[str, object]
MessageHandler = Callable[[JsonDict, Tuple[str, int]], None]


class UDPServer:
    def __init__(self, host: str, port: int, handler: Optional[MessageHandler], client_ttl: float = 30.0) -> None:
        self.host = host
        self.port = port
        self.client_ttl = client_ttl
        self._handler = handler
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._clients: Dict[Tuple[str, int], float] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.settimeout(0.5)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._socket:
            try:
                self._socket.close()
            finally:
                self._socket = None
        with self._lock:
            self._clients.clear()

    def send_to(self, addr: Tuple[str, int], message: JsonDict) -> None:
        self._sendto(json.dumps(message).encode("utf-8"), addr)

    def broadcast(self, message: JsonDict) -> None:
        data = json.dumps(message).encode("utf-8")
        now = time.time()
        with self._lock:
            stale = [addr for addr, ts in self._clients.items() if now - ts > self.client_ttl]
            for addr in stale:
                del self._clients[addr]
            clients = list(self._clients.keys())
        for addr in clients:
            self._sendto(data, addr)

    def get_connected_clients(self) -> list[Tuple[str, int]]:
        with self._lock:
            return list(self._clients.keys())

    def _serve_forever(self) -> None:
        assert self._socket is not None
        while not self._stop_event.is_set():
            try:
                data, addr = self._socket.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                decoded = data.decode("utf-8").strip()
                message = json.loads(decoded)
                if not isinstance(message, dict):
                    raise ValueError("message is not a JSON object")
            except Exception as exc:
                self.send_to(addr, {"type": "error", "data": {"message": f"Invalid message: {exc}"}})
                continue
            with self._lock:
                self._clients[addr] = time.time()
            if self._handler:
                self._handler(message, addr)

    def _sendto(self, data: bytes, addr: Tuple[str, int]) -> None:
        if self._socket is None:
            return
        try:
            self._socket.sendto(data, addr)
        except OSError:
            with self._lock:
                self._clients.pop(addr, None)
