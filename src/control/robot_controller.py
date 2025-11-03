#!/usr/bin/env python3
"""
TCP Robot Controller
Manages TCP server connection to robot and sends movement commands.
"""

import socket
import threading
import json


class RobotController:
    """TCP server for multiple robots to connect to."""
    
    def __init__(self, host='0.0.0.0', port=6969, robots=None):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_sockets = {}
        self.connected = False
        self.running = False
        self.server_thread = None
        self.clients_lock = threading.Lock()
        self.robots = robots or {}
        
    def start_server(self):
        """Start TCP server and wait for robot connection."""
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        return True
    
    def _run_server(self):
        """Run TCP server for multiple robots."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.server_socket.settimeout(1.0)
            print(f"[Controller] ✓ TCP Server listening on {self.host}:{self.port}")
            print(f"[Controller] Waiting for robots to connect...")
        except OSError as e:
            print(f"[Controller] ✗ Server error: {e}")
            self.running = False
            return
        
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                thread = threading.Thread(target=self._handle_client, args=(client_socket, address), daemon=True)
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[Controller] Server error: {e}")
        
        if self.server_socket:
            self.server_socket.close()
    
    def _handle_client(self, client_socket, address):
        """Handle individual client connection."""
        connecting_ip = address[0]
        print(f"[Controller] 🔌 New TCP connection from {connecting_ip}:{address[1]}")
        
        robot_name = None
        for name, robot in self.robots.items():
            if robot.robot_type == 'real':
                print(f"[Controller]    Checking {name}: configured IP={robot.ip}, connecting IP={connecting_ip}")
                if robot.ip == connecting_ip:
                    robot_name = name
                    print(f"[Controller]    ✓ Matched to robot: {name}")
                    break
        
        if not robot_name:
            # Try to find by checking if there's only one real robot
            real_robots = [name for name, r in self.robots.items() if r.robot_type == 'real']
            if len(real_robots) == 1:
                robot_name = real_robots[0]
                print(f"[Controller]    ✓ Auto-assigned to only real robot: {robot_name}")
            else:
                robot_name = f"robot_{connecting_ip}"
                print(f"[Controller]    ⚠️ Could not match IP, using generic name: {robot_name}")
        
        with self.clients_lock:
            self.client_sockets[robot_name] = client_socket
            self.connected = len(self.client_sockets) > 0
            print(f"[Controller] ✅ Robot '{robot_name}' connected from {address}")
        
        try:
            while self.running:
                client_socket.settimeout(5.0)
                try:
                    data = client_socket.recv(1024)
                    if not data:
                        print(f"[Controller] Robot {robot_name} closed connection")
                        break
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[Controller] Robot {robot_name} error: {e}")
                    break
        except Exception as e:
            print(f"[Controller] Robot {robot_name} handler exception: {e}")
        
        with self.clients_lock:
            if robot_name in self.client_sockets:
                del self.client_sockets[robot_name]
            self.connected = len(self.client_sockets) > 0
            print(f"[Controller] 🔌 Robot {robot_name} disconnected")
    
    def send_command(self, throttle, angle, robot_name=None):
        """
        Send command to robot(s).
        
        Args:
            throttle: forward command ratio in [0, 1]
            angle: turn rate in degrees/second (will be inverted for robot)
            robot_name: specific robot name, or None for all robots
        
        Returns:
            bool: True if command sent successfully
        """
        try:
            throttle_val = float(throttle)
        except (TypeError, ValueError):
            throttle_val = 0.0
        throttle_val = max(-1.0, min(1.0, throttle_val))
        legacy_direction = 1 if throttle_val > 1e-3 else 0
        cmd = {"throttle": throttle_val, "direction": legacy_direction, "angle": angle}
        msg = json.dumps(cmd) + '\n'
        
        success = False
        with self.clients_lock:
            if robot_name:
                if robot_name in self.client_sockets:
                    try:
                        self.client_sockets[robot_name].sendall(msg.encode('utf-8'))
                        success = True
                    except Exception as e:
                        print(f"[Controller] ✗ Send to {robot_name} failed: {e}")
                        del self.client_sockets[robot_name]
                        self.connected = len(self.client_sockets) > 0
                if robot_name in self.robots and self.robots[robot_name].robot_type == 'dummy':
                    self.robots[robot_name].set_command(throttle_val, angle)
                    success = True
            else:
                for name, socket_obj in list(self.client_sockets.items()):
                    try:
                        socket_obj.sendall(msg.encode('utf-8'))
                        success = True
                    except Exception as e:
                        print(f"[Controller] ✗ Send to {name} failed: {e}")
                        del self.client_sockets[name]
                for name, robot in self.robots.items():
                    if robot.robot_type == 'dummy':
                        robot.set_command(throttle_val, angle)
                        success = True
                self.connected = len(self.client_sockets) > 0
        
        return success
    
    def shutdown(self):
        """Shutdown server."""
        self.running = False
        
        with self.clients_lock:
            for socket_obj in self.client_sockets.values():
                try:
                    socket_obj.close()
                except:
                    pass
            self.client_sockets.clear()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
