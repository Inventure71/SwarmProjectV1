#!/usr/bin/env python3
"""
TCP Robot Controller
Manages TCP server connection to robot and sends movement commands.
"""

import socket
import threading
import json


class RobotController:
    """TCP server for robot to connect to."""
    
    def __init__(self, host='0.0.0.0', port=6969):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.connected = False
        self.running = False
        self.server_thread = None
        self.clients_lock = threading.Lock()
        
    def start_server(self):
        """Start TCP server and wait for robot connection."""
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        return True
    
    def _run_server(self):
        """Run TCP server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)
            print(f"[Controller] ✓ TCP Server listening on {self.host}:{self.port}")
            print(f"[Controller] Waiting for robot to connect...")
        except OSError as e:
            print(f"[Controller] ✗ Server error: {e}")
            self.running = False
            return
        
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                with self.clients_lock:
                    if self.client_socket:
                        try:
                            self.client_socket.close()
                        except:
                            pass
                    
                    self.client_socket = client_socket
                    self.connected = True
                    print(f"[Controller] ✓ Robot connected from {address}")
                
                while self.running and self.connected:
                    try:
                        client_socket.settimeout(1.0)
                        data = client_socket.recv(1)
                        if not data:
                            break
                    except socket.timeout:
                        continue
                    except Exception:
                        break
                
                with self.clients_lock:
                    self.connected = False
                    self.client_socket = None
                print(f"[Controller] Robot disconnected")
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[Controller] Server error: {e}")
        
        if self.server_socket:
            self.server_socket.close()
    
    def send_command(self, throttle, angle):
        """
        Send command to robot.
        
        Args:
            throttle: forward command ratio in [0, 1]
            angle: turn rate in degrees/second (will be inverted for robot)
        
        Returns:
            bool: True if command sent successfully
        """
        with self.clients_lock:
            if not self.connected or not self.client_socket:
                return False
            try:
                try:
                    throttle_val = float(throttle)
                except (TypeError, ValueError):
                    throttle_val = 0.0
                throttle_val = max(-1.0, min(1.0, throttle_val))
                legacy_direction = 1 if throttle_val > 1e-3 else 0
                # Invert angle: robot expects positive = left, we use positive = right
                cmd = {"throttle": throttle_val, "direction": legacy_direction, "angle": angle}
                msg = json.dumps(cmd) + '\n'
                self.client_socket.sendall(msg.encode('utf-8'))
                return True
            except Exception as e:
                print(f"[Controller] ✗ Send failed: {e}")
                self.connected = False
                self.client_socket = None
                return False
    
    def shutdown(self):
        """Shutdown server."""
        self.running = False
        
        with self.clients_lock:
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
            self.client_socket = None
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
