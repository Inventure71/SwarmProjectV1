#!/usr/bin/env python3
"""UDP client for communicating with the Mosaic supervisor bridge."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections import defaultdict
from queue import Queue, Empty
from typing import Callable, DefaultDict, Dict, List, Optional


JsonDict = Dict[str, object]
MessageCallback = Callable[[JsonDict], None]


class UDPClient:
    """Threaded UDP JSON client with state caching and callbacks."""

    def __init__(
        self,
        host: str,
        port: int,
        on_message: Optional[MessageCallback] = None,
        socket_timeout: float = 0.5,
        heartbeat_interval: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.socket_timeout = socket_timeout
        self.on_message = on_message
        self.heartbeat_interval = heartbeat_interval

        self._socket: Optional[socket.socket] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._callbacks: DefaultDict[str, List[MessageCallback]] = defaultdict(list)
        self._ack_queue: "Queue[JsonDict]" = Queue()

        self._state_lock = threading.Lock()
        self._robot_states: Dict[str, Dict[str, float]] = {}
        self._follower_states: Dict[str, Dict[str, float]] = {}
        self._connection_status: Dict[str, object] = {}
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._listener_thread and self._listener_thread.is_alive():
            return

        try:
            self._create_socket()
        except Exception as exc:
            print(f"[UDPClient] Failed to connect: {exc}")
            raise

        self._stop_event.clear()
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()

        # Start heartbeat thread to maintain connection
        if self.heartbeat_interval > 0:
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._heartbeat_thread.start()

        # Send hello to register with the supervisor bridge
        self.send({"type": "hello", "data": {"timestamp": time.time()}})

    def close(self) -> None:
        self._stop_event.set()
        if self._listener_thread:
            self._listener_thread.join(timeout=1.0)
            self._listener_thread = None
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1.0)
            self._heartbeat_thread = None

        if self._socket:
            try:
                self._socket.close()
            finally:
                self._socket = None

    # ------------------------------------------------------------------
    # Communication helpers
    # ------------------------------------------------------------------

    def send(self, message: JsonDict) -> None:
        data = json.dumps(message).encode("utf-8")
        if not self._socket:
            try:
                self._create_socket()
            except Exception as exc:
                self._last_error = f"Socket creation failed: {exc}"
                print(f"[UDPClient] ERROR: {self._last_error}")
                return
        assert self._socket is not None
        try:
            self._socket.sendto(data, (self.host, self.port))
        except OSError as exc:
            self._last_error = str(exc)
            print(f"[UDPClient] ERROR sending: {exc}")

    def wait_for_ack(self, command: Optional[str] = None, timeout: float = 1.0) -> Optional[JsonDict]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                ack = self._ack_queue.get(timeout=0.1)
            except Empty:
                continue
            if command is None or ack.get("data", {}).get("command") == command:
                return ack
        return None

    def register_callback(self, message_type: str, callback: MessageCallback) -> None:
        self._callbacks[message_type].append(callback)

    # ------------------------------------------------------------------
    # Cached state accessors
    # ------------------------------------------------------------------

    def get_robot_states(self) -> Dict[str, Dict[str, float]]:
        with self._state_lock:
            return dict(self._robot_states)

    def get_follower_states(self) -> Dict[str, Dict[str, float]]:
        with self._state_lock:
            return dict(self._follower_states)

    def get_connection_status(self) -> Dict[str, object]:
        with self._state_lock:
            return dict(self._connection_status)

    def get_last_error(self) -> Optional[str]:
        return self._last_error

    # ------------------------------------------------------------------
    # Internal logic
    # ------------------------------------------------------------------

    def _create_socket(self) -> None:
        if self._socket:
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.socket_timeout)
            # Bind to any available port (0 = let OS choose)
            # Note: UDP requires binding to receive messages - this is not a "server",
            # just a way to receive responses from the supervisor bridge
            sock.bind(('', 0))
            self._socket = sock
            print(f"[UDPClient] Connected to supervisor bridge at {self.host}:{self.port}")
        except Exception as exc:
            self._last_error = f"Failed to create socket: {exc}"
            print(f"[UDPClient] ERROR: {self._last_error}")
            raise

    def _listen_loop(self) -> None:
        assert self._socket is not None
        while not self._stop_event.is_set():
            try:
                data, addr = self._socket.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError as exc:
                self._last_error = str(exc)
                if not self._stop_event.is_set():
                    print(f"[UDPClient] Connection error: {exc}")
                break

            try:
                message = json.loads(data.decode("utf-8"))
                if not isinstance(message, dict):
                    raise ValueError("Message is not a JSON object")
            except Exception:
                self._last_error = "Failed to decode message"
                continue

            self._dispatch_message(message)

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat messages to keep connection alive."""
        while not self._stop_event.is_set():
            try:
                self.send({"type": "ping", "data": {"timestamp": time.time()}})
            except Exception as exc:
                if not self._stop_event.is_set():
                    print(f"[UDPClient] Heartbeat failed: {exc}")
            
            # Sleep in small intervals to allow quick shutdown
            elapsed = 0.0
            while elapsed < self.heartbeat_interval and not self._stop_event.is_set():
                time.sleep(0.5)
                elapsed += 0.5

    def _dispatch_message(self, message: JsonDict) -> None:
        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "robot_states" and isinstance(data, dict):
            with self._state_lock:
                self._robot_states = data
        elif msg_type == "path_following_state" and isinstance(data, dict):
            with self._state_lock:
                self._follower_states = data
        elif msg_type == "connection_status" and isinstance(data, dict):
            with self._state_lock:
                self._connection_status = data
        elif msg_type == "error":
            self._last_error = str(data.get("message")) if isinstance(data, dict) else str(data)
        elif msg_type == "ack":
            self._ack_queue.put(message)

        if self.on_message:
            self.on_message(message)

        for callback in self._callbacks.get(msg_type, []):
            try:
                callback(message)
            except Exception:
                pass


__all__ = ["UDPClient"]

