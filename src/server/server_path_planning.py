#!/usr/bin/env python3
"""
Path Planning Server with Canvas Drawing

Features:
- Click on canvas to draw waypoints
- Robot follows the drawn path
- Real-time position tracking from OptiTrack
- Visual feedback of robot position and path
"""

import socket
import threading
import json
import sys
import tkinter as tk
import math
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.config_loader import load_config
from optitrack.tracker import RobotTracker


class PathPlanningCanvas(tk.Canvas):
    """Canvas for drawing paths and showing robot position."""
    
    def __init__(self, parent, width=700, height=600, **kwargs):
        super().__init__(parent, width=width, height=height, bg='#1a1a1a', **kwargs)
        self.width = width
        self.height = height
        
        # Map bounds (meters)
        self.map_min_x = -10.0
        self.map_max_x = 10.0
        self.map_min_y = -10.0
        self.map_max_y = 10.0
        
        # Drawing state
        self.drawing = False
        self.drawn_path = []  # Raw drawn points
        self.path_line = None
        
        # Waypoints (simplified path)
        self.waypoints = []
        self.waypoint_circles = []
        
        # Robot markers
        self.robot_marker = None
        self.robot_arrow = None
        self.robot_color = '#00ff00'
        
        self._draw_grid()
        
        # Bind mouse events for drawing
        self.bind('<Button-1>', self._on_mouse_down)
        self.bind('<B1-Motion>', self._on_mouse_drag)
        self.bind('<ButtonRelease-1>', self._on_mouse_up)
    
    def _draw_grid(self):
        """Draw grid."""
        for i in range(-10, 11, 2):
            x = self._map_to_canvas_x(float(i))
            self.create_line(x, 0, x, self.height, fill='#333', width=1)
            
            y = self._map_to_canvas_y(float(i))
            self.create_line(0, y, self.width, y, fill='#333', width=1)
        
        center_x = self._map_to_canvas_x(0.0)
        center_y = self._map_to_canvas_y(0.0)
        self.create_line(center_x, 0, center_x, self.height, fill='#666', width=2)
        self.create_line(0, center_y, self.width, center_y, fill='#666', width=2)
        
        self.create_text(self.width - 10, center_y - 10, text="+X", fill='#999', anchor='se')
        self.create_text(center_x + 10, 10, text="+Y", fill='#999', anchor='nw')
    
    def _map_to_canvas_x(self, x):
        ratio = (x - self.map_min_x) / (self.map_max_x - self.map_min_x)
        return ratio * self.width
    
    def _map_to_canvas_y(self, y):
        ratio = (y - self.map_min_y) / (self.map_max_y - self.map_min_y)
        return self.height - (ratio * self.height)
    
    def _canvas_to_map_x(self, x):
        ratio = x / self.width
        return self.map_min_x + ratio * (self.map_max_x - self.map_min_x)
    
    def _canvas_to_map_y(self, y):
        ratio = (self.height - y) / self.height
        return self.map_min_y + ratio * (self.map_max_y - self.map_min_y)
    
    def _on_mouse_down(self, event):
        """Start drawing."""
        self.drawing = True
        map_x = self._canvas_to_map_x(event.x)
        map_y = self._canvas_to_map_y(event.y)
        self.drawn_path = [(map_x, map_y)]
    
    def _on_mouse_drag(self, event):
        """Continue drawing."""
        if not self.drawing:
            return
        
        map_x = self._canvas_to_map_x(event.x)
        map_y = self._canvas_to_map_y(event.y)
        self.drawn_path.append((map_x, map_y))
        
        # Redraw path
        if self.path_line:
            self.delete(self.path_line)
        
        if len(self.drawn_path) > 1:
            canvas_points = []
            for x, y in self.drawn_path:
                canvas_points.append(self._map_to_canvas_x(x))
                canvas_points.append(self._map_to_canvas_y(y))
            
            self.path_line = self.create_line(
                *canvas_points,
                fill='#ff4444', width=3, smooth=True
            )
    
    def _on_mouse_up(self, event):
        """Finish drawing."""
        self.drawing = False
    
    def clear_path(self):
        """Clear all paths."""
        # Clear drawn path
        if self.path_line:
            self.delete(self.path_line)
            self.path_line = None
        self.drawn_path = []
        
        # Clear waypoints
        for item in self.waypoint_circles:
            self.delete(item)
        self.waypoints = []
        self.waypoint_circles = []
    
    def straighten_path(self):
        """Convert drawn path to simplified waypoints using Douglas-Peucker algorithm."""
        if len(self.drawn_path) < 2:
            return
        
        # Clear existing waypoints
        for item in self.waypoint_circles:
            self.delete(item)
        self.waypoint_circles = []
        
        # Simplify path
        tolerance = 0.2  # meters
        self.waypoints = self._douglas_peucker(self.drawn_path, tolerance)
        
        # Draw waypoints
        for idx, (x, y) in enumerate(self.waypoints):
            canvas_x = self._map_to_canvas_x(x)
            canvas_y = self._map_to_canvas_y(y)
            
            # Draw waypoint circle
            r = 8
            circle = self.create_oval(
                canvas_x - r, canvas_y - r,
                canvas_x + r, canvas_y + r,
                fill='#00ff00', outline='#fff', width=2
            )
            self.waypoint_circles.append(circle)
            
            # Draw number
            num_text = self.create_text(
                canvas_x, canvas_y - 15,
                text=str(idx + 1),
                fill='#fff',
                font=('Arial', 10, 'bold')
            )
            self.waypoint_circles.append(num_text)
    
    def _douglas_peucker(self, points, tolerance):
        """Simplify path using Douglas-Peucker algorithm."""
        if len(points) < 3:
            return points
        
        # Find point with maximum distance from line
        dmax = 0
        index = 0
        end = len(points) - 1
        
        for i in range(1, end):
            d = self._perpendicular_distance(points[i], points[0], points[end])
            if d > dmax:
                index = i
                dmax = d
        
        # If max distance is greater than tolerance, recursively simplify
        if dmax > tolerance:
            # Recursive call
            rec_results1 = self._douglas_peucker(points[:index+1], tolerance)
            rec_results2 = self._douglas_peucker(points[index:], tolerance)
            
            # Build result list
            result = rec_results1[:-1] + rec_results2
        else:
            result = [points[0], points[end]]
        
        return result
    
    def _perpendicular_distance(self, point, line_start, line_end):
        """Calculate perpendicular distance from point to line."""
        x, y = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        # Calculate distance
        num = abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1)
        den = math.sqrt((y2 - y1)**2 + (x2 - x1)**2)
        
        if den == 0:
            return 0
        
        return num / den
    
    def update_robot(self, x, y, yaw):
        """Update robot position."""
        canvas_x = self._map_to_canvas_x(x)
        canvas_y = self._map_to_canvas_y(y)
        
        if self.robot_marker:
            self.delete(self.robot_marker)
            self.delete(self.robot_arrow)
        
        # Robot circle
        r = 12
        self.robot_marker = self.create_oval(
            canvas_x - r, canvas_y - r,
            canvas_x + r, canvas_y + r,
            fill=self.robot_color, outline='#fff', width=2
        )
        
        # Direction arrow
        arrow_len = 30
        end_x = canvas_x + arrow_len * math.cos(yaw)
        end_y = canvas_y - arrow_len * math.sin(yaw)
        self.robot_arrow = self.create_line(
            canvas_x, canvas_y, end_x, end_y,
            fill=self.robot_color, width=3,
            arrow=tk.LAST, arrowshape=(12, 15, 5)
        )


class PathPlanningServer:
    """Server for path planning and following."""
    
    def __init__(self, host='0.0.0.0', port=6969):
        self.host = host
        self.port = port
        self.clients = []
        self.clients_lock = threading.Lock()
        self.running = True
        
        # Path following state
        self.following = False
        self.current_waypoint_idx = 0
        self.target_threshold = 0.25  # meters - increased for tracking noise
        self.approach_distance = 0.5  # meters - slow down zone
        self.linear_speed = 0.3  # m/s
        self.max_angular_speed = 45.0  # deg/s - reduced for smoother control
        self.min_angular_speed = 5.0  # deg/s - minimum turn speed
        self.angle_deadband = 5.0  # degrees - ignore tiny angle errors
        
        # Control state for smoothing
        self.last_direction = 0
        self.last_angular = 0.0
        self.stable_count = 0
        
        # Load config and tracker
        print("\n" + "="*70)
        print("[Server] 🚀 STARTING PATH PLANNING SERVER")
        print("="*70)
        self.config = load_config()
        robot_config = self.config.get_robot_config()
        
        print(f"[Server] Found {len(robot_config)} robots")
        
        # Use first robot for now
        self.robot_name = list(robot_config.keys())[0]
        print(f"[Server] Using robot: {self.robot_name}")
        
        self.tracker = RobotTracker(robot_config)
        self.robots = self.tracker.robots
        self.robot = self.robots[self.robot_name]
        
        print("[Server] Starting tracker...")
        self.tracker.start()
        print("[Server] ✓ Tracking active\n")
        
        # Setup GUI
        self.root = tk.Tk()
        self.root.title("Path Planning Server")
        self.root.configure(bg='#1e1e1e')
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        
        self._setup_ui()
        
        # Start TCP server
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        # Update loop
        self.root.after(100, self._update)
    
    def _setup_ui(self):
        """Setup UI."""
        # Title
        title = tk.Label(
            self.root,
            text="🎯 Path Planning & Following",
            font=('Arial', 18, 'bold'),
            bg='#1e1e1e',
            fg='#fff'
        )
        title.pack(pady=10)
        
        # Status
        self.status_label = tk.Label(
            self.root,
            text=f"Robot: {self.robot_name} | Clients: 0",
            font=('Arial', 11),
            bg='#1e1e1e',
            fg='#4CAF50'
        )
        self.status_label.pack(pady=5)
        
        # Instructions
        instructions = tk.Label(
            self.root,
            text="Draw path by clicking and dragging • Click 'Straighten' to create waypoints • Start to follow",
            font=('Arial', 10),
            bg='#1e1e1e',
            fg='#888'
        )
        instructions.pack(pady=5)
        
        # Canvas
        self.canvas = PathPlanningCanvas(self.root, width=700, height=600)
        self.canvas.pack(pady=10)
        
        # Control panel
        control_frame = tk.Frame(self.root, bg='#1e1e1e')
        control_frame.pack(pady=10)
        
        # Row 1: Drawing controls
        draw_frame = tk.Frame(control_frame, bg='#1e1e1e')
        draw_frame.pack(pady=5)
        
        straighten_btn = tk.Button(
            draw_frame,
            text="📏 Straighten Path",
            font=('Arial', 12, 'bold'),
            bg='#2196F3',
            fg='#fff',
            command=self._straighten_path,
            padx=20,
            pady=10
        )
        straighten_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = tk.Button(
            draw_frame,
            text="🗑 Clear All",
            font=('Arial', 12),
            bg='#f44336',
            fg='#fff',
            command=self._clear_path,
            padx=20,
            pady=10
        )
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Row 2: Following controls
        follow_frame = tk.Frame(control_frame, bg='#1e1e1e')
        follow_frame.pack(pady=5)
        
        self.start_btn = tk.Button(
            follow_frame,
            text="▶ Start Following",
            font=('Arial', 12, 'bold'),
            bg='#4CAF50',
            fg='#fff',
            command=self._start_following,
            padx=20,
            pady=10
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(
            follow_frame,
            text="⏸ Stop",
            font=('Arial', 12, 'bold'),
            bg='#ff9800',
            fg='#fff',
            command=self._stop_following,
            padx=20,
            pady=10,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        quit_btn = tk.Button(
            follow_frame,
            text="Quit",
            font=('Arial', 12),
            bg='#555',
            fg='#fff',
            command=self.shutdown,
            padx=20,
            pady=10
        )
        quit_btn.pack(side=tk.LEFT, padx=5)
        
        # Info display
        info_frame = tk.Frame(self.root, bg='#2b2b2b')
        info_frame.pack(pady=10, padx=20, fill=tk.BOTH)
        
        self.info_text = tk.Text(
            info_frame,
            height=4,
            width=100,
            bg='#2b2b2b',
            fg='#00ff00',
            font=('Courier', 10),
            relief=tk.FLAT,
            state=tk.DISABLED
        )
        self.info_text.pack(pady=5)
    
    def _update(self):
        """Update loop."""
        if not self.running:
            return
        
        # Update robot position
        x, y, yaw_degrees = self.robot.get_position()
        # Convert to radians for canvas drawing
        yaw_rad = yaw_degrees * math.pi / 180.0
        self.canvas.update_robot(x, y, yaw_rad)
        
        # Update status
        with self.clients_lock:
            client_count = len(self.clients)
        self.status_label.config(
            text=f"Robot: {self.robot_name} | Clients: {client_count} | Following: {'YES' if self.following else 'NO'}"
        )
        
        # Update info
        drawn_points = len(self.canvas.drawn_path)
        waypoint_count = len(self.canvas.waypoints)
        
        if self.following and waypoint_count > 0:
            target_x, target_y = self.canvas.waypoints[self.current_waypoint_idx]
            dist = math.sqrt((target_x - x)**2 + (target_y - y)**2)
            info = f"Position: ({x:.3f}, {y:.3f}, {yaw_degrees:.1f}°)\n"
            info += f"Waypoint: {self.current_waypoint_idx + 1}/{waypoint_count}\n"
            info += f"Target: ({target_x:.3f}, {target_y:.3f})\n"
            info += f"Distance: {dist:.3f}m"
        else:
            info = f"Position: ({x:.3f}, {y:.3f}, {yaw_degrees:.1f}°)\n"
            info += f"Drawn points: {drawn_points} | Waypoints: {waypoint_count}\n"
            if drawn_points > 0 and waypoint_count == 0:
                info += "Status: Draw complete - Click 'Straighten' to create waypoints\n"
            elif waypoint_count > 0:
                info += "Status: Ready - Click 'Start Following' to begin\n"
            else:
                info += "Status: Draw path by clicking and dragging on canvas"
        
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info)
        self.info_text.config(state=tk.DISABLED)
        
        # Path following logic
        if self.following:
            self._follow_path()
        
        self.root.after(100, self._update)
    
    def _follow_path(self):
        """Execute path following with delay compensation and smooth control."""
        if not self.canvas.waypoints:
            self._stop_following()
            return
        
        if self.current_waypoint_idx >= len(self.canvas.waypoints):
            print("[PathFollow] ✓ Reached end of path")
            self._stop_following()
            self.broadcast_command(0, 0.0)
            return
        
        # Get current state
        x, y, yaw_degrees = self.robot.get_position()
        target_x, target_y = self.canvas.waypoints[self.current_waypoint_idx]
        
        # Convert yaw from degrees to radians (OptiTrack sends degrees!)
        yaw_rad = yaw_degrees * math.pi / 180.0
        
        # Calculate distance and angle to target
        dx = target_x - x
        dy = target_y - y
        distance = math.sqrt(dx**2 + dy**2)
        target_angle_rad = math.atan2(dy, dx)
        
        # Calculate angle error (in radians)
        angle_error_rad = target_angle_rad - yaw_rad
        # Normalize to [-pi, pi]
        while angle_error_rad > math.pi:
            angle_error_rad -= 2 * math.pi
        while angle_error_rad < -math.pi:
            angle_error_rad += 2 * math.pi
        
        # Convert to degrees for control
        angle_error_deg = angle_error_rad * 180.0 / math.pi
        
        # Check if reached waypoint (with margin for tracking noise)
        if distance < self.target_threshold:
            # Require stable arrival (3 consecutive measurements within threshold)
            self.stable_count += 1
            if self.stable_count >= 3:
                print(f"[PathFollow] ✓ Reached waypoint {self.current_waypoint_idx + 1} (stable)")
                self.current_waypoint_idx += 1
                self.stable_count = 0
                self.last_direction = 0
                self.last_angular = 0.0
                return
        else:
            self.stable_count = 0
        
        # Apply deadband to angle error (ignore micro-movements)
        if abs(angle_error_deg) < self.angle_deadband:
            angle_error_deg = 0.0
        
        # Calculate angular speed with adaptive P-gain
        # Reduce gain when close to target to avoid overshooting
        if distance < self.approach_distance:
            p_gain = 1.0  # Slower when close
        else:
            p_gain = 1.5  # Normal speed
        
        angular_speed_deg = angle_error_deg * p_gain
        
        # Apply minimum speed threshold (avoid tiny movements)
        if abs(angular_speed_deg) > 0 and abs(angular_speed_deg) < self.min_angular_speed:
            angular_speed_deg = math.copysign(self.min_angular_speed, angular_speed_deg)
        
        # Clamp to maximum angular speed
        angular_speed_deg = max(-self.max_angular_speed, min(self.max_angular_speed, angular_speed_deg))
        
        # Smooth the angular speed (exponential moving average)
        alpha = 0.3  # Smoothing factor
        angular_speed_deg = alpha * angular_speed_deg + (1 - alpha) * self.last_angular
        self.last_angular = angular_speed_deg
        
        # Decide whether to move forward or just rotate
        # More conservative angle threshold (30 degrees instead of 20)
        if abs(angle_error_deg) > 30:
            direction = 0  # Stop and rotate in place
        elif distance < self.approach_distance:
            # When close, move slowly
            direction = 1 if abs(angle_error_deg) < 15 else 0
        else:
            direction = 1  # Move forward while correcting
        
        # Avoid rapid switching between states
        if direction != self.last_direction:
            # Add hysteresis - require 2 consecutive changes
            if not hasattr(self, '_direction_change_count'):
                self._direction_change_count = 0
            self._direction_change_count += 1
            if self._direction_change_count < 2:
                direction = self.last_direction
            else:
                self._direction_change_count = 0
                self.last_direction = direction
        else:
            if hasattr(self, '_direction_change_count'):
                self._direction_change_count = 0
        
        # Debug output every 10 updates
        if not hasattr(self, '_debug_counter'):
            self._debug_counter = 0
        self._debug_counter += 1
        if self._debug_counter % 10 == 0:
            target_angle_deg = target_angle_rad * 180.0 / math.pi
            print(f"[PathFollow] WP {self.current_waypoint_idx + 1}/{len(self.canvas.waypoints)}")
            print(f"[PathFollow] Pos: ({x:.2f},{y:.2f},{yaw_degrees:.1f}°), Target: ({target_x:.2f},{target_y:.2f},{target_angle_deg:.1f}°)")
            print(f"[PathFollow] Dist: {distance:.3f}m, AngleErr: {angle_error_deg:.1f}°, Turn: {angular_speed_deg:.1f}°/s, Dir: {direction}")
        
        # Note: Positive angle_error means target is to the LEFT (counterclockwise)
        # But joystick convention: positive = turn RIGHT
        # So we negate the angle for the command
        self.broadcast_command(direction, -angular_speed_deg)
    
    def _start_following(self):
        """Start following path."""
        if not self.canvas.waypoints:
            print("[Server] No waypoints to follow")
            return
        
        print(f"[Server] Starting path following ({len(self.canvas.waypoints)} waypoints)")
        self.following = True
        self.current_waypoint_idx = 0
        
        # Reset control state
        self.last_direction = 0
        self.last_angular = 0.0
        self.stable_count = 0
        if hasattr(self, '_direction_change_count'):
            self._direction_change_count = 0
        if hasattr(self, '_debug_counter'):
            self._debug_counter = 0
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
    
    def _stop_following(self):
        """Stop following path."""
        print("[Server] Stopped path following")
        self.following = False
        self.broadcast_command(0, 0.0)
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def _straighten_path(self):
        """Straighten drawn path into waypoints."""
        if not self.canvas.drawn_path:
            print("[Server] No path drawn to straighten")
            return
        
        self.canvas.straighten_path()
        print(f"[Server] Straightened path into {len(self.canvas.waypoints)} waypoints")
    
    def _clear_path(self):
        """Clear path."""
        self._stop_following()
        self.canvas.clear_path()
        print("[Server] Cleared path")
    
    def broadcast_command(self, direction, angle):
        """Broadcast command."""
        cmd = {"direction": direction, "angle": angle}
        msg = json.dumps(cmd) + '\n'
        
        with self.clients_lock:
            dead_clients = []
            for client in self.clients:
                try:
                    client.sendall(msg.encode('utf-8'))
                except Exception:
                    dead_clients.append(client)
            
            for client in dead_clients:
                self.clients.remove(client)
                try:
                    client.close()
                except:
                    pass
    
    def handle_client(self, client_socket, address):
        """Handle client."""
        print(f"[Server] Robot connected: {address}")
        with self.clients_lock:
            self.clients.append(client_socket)
        
        try:
            while self.running:
                client_socket.settimeout(1.0)
                try:
                    data = client_socket.recv(1)
                    if not data:
                        break
                except socket.timeout:
                    continue
        except Exception as e:
            print(f"[Server] Client error: {e}")
        finally:
            with self.clients_lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
            client_socket.close()
            print(f"[Server] Robot disconnected: {address}")
    
    def _run_server(self):
        """Run TCP server."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            server_socket.settimeout(1.0)
            print(f"[Server] ✓ TCP Server: {self.host}:{self.port}\n")
        except OSError as e:
            print(f"[Server] ERROR: {e}")
            self.running = False
            return
        
        while self.running:
            try:
                client_socket, address = server_socket.accept()
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[Server] Error: {e}")
        
        server_socket.close()
    
    def shutdown(self):
        """Shutdown."""
        print("\n[Server] Shutting down...")
        self.running = False
        self._stop_following()
        
        with self.clients_lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
        
        self.tracker.stop()
        self.root.quit()
    
    def run(self):
        """Run server."""
        print("[Server] GUI started\n")
        self.root.mainloop()


def main():
    port = 6969
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)
    
    server = PathPlanningServer(host='0.0.0.0', port=port)
    server.run()


if __name__ == '__main__':
    main()

