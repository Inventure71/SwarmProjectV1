#!/usr/bin/env python3
"""
Advanced Robot Control Server with OptiTrack Tracking & Map UI

Features:
- Real-time 2D map showing robot positions from OptiTrack
- Joystick control for direction and turning
- Speed slider for linear velocity
- Visual feedback of robot states
- TCP server for broadcasting commands
"""

import socket
import threading
import json
import sys
import tkinter as tk
from tkinter import ttk
import math
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.config_loader import load_config
from optitrack.tracker import RobotTracker


class MapWidget(tk.Canvas):
    """2D Map widget showing robot positions."""
    
    def __init__(self, parent, width=600, height=600, **kwargs):
        super().__init__(parent, width=width, height=height, bg='#1a1a1a', **kwargs)
        self.width = width
        self.height = height
        
        # Map bounds (in meters)
        self.map_min_x = -10.0
        self.map_max_x = 10.0
        self.map_min_y = -10.0
        self.map_max_y = 10.0
        
        # Robot markers
        self.robot_markers = {}  # {name: (circle_id, text_id, arrow_id)}
        self.robot_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F']
        self.color_index = 0
        
        self._draw_grid()
        
    def _draw_grid(self):
        """Draw grid lines on the map."""
        # Draw grid
        for i in range(-10, 11, 2):
            # Vertical lines
            x = self._map_to_canvas_x(float(i))
            self.create_line(x, 0, x, self.height, fill='#333', width=1)
            
            # Horizontal lines
            y = self._map_to_canvas_y(float(i))
            self.create_line(0, y, self.width, y, fill='#333', width=1)
        
        # Draw axes
        center_x = self._map_to_canvas_x(0.0)
        center_y = self._map_to_canvas_y(0.0)
        self.create_line(center_x, 0, center_x, self.height, fill='#666', width=2)
        self.create_line(0, center_y, self.width, center_y, fill='#666', width=2)
        
        # Labels
        self.create_text(self.width - 10, center_y - 10, text="+X", fill='#999', anchor='se')
        self.create_text(center_x + 10, 10, text="+Y", fill='#999', anchor='nw')
    
    def _map_to_canvas_x(self, x):
        """Convert map X coordinate to canvas X."""
        ratio = (x - self.map_min_x) / (self.map_max_x - self.map_min_x)
        return ratio * self.width
    
    def _map_to_canvas_y(self, y):
        """Convert map Y coordinate to canvas Y (inverted)."""
        ratio = (y - self.map_min_y) / (self.map_max_y - self.map_min_y)
        return self.height - (ratio * self.height)  # Invert Y
    
    def add_robot(self, name):
        """Add a robot to the map."""
        if name not in self.robot_markers:
            color = self.robot_colors[self.color_index % len(self.robot_colors)]
            self.color_index += 1
            
            # Create robot marker (circle)
            circle = self.create_oval(0, 0, 20, 20, fill=color, outline='#fff', width=2)
            
            # Create label
            text = self.create_text(0, 0, text=name, fill='#fff', font=('Arial', 8, 'bold'))
            
            # Create direction arrow
            arrow = self.create_line(0, 0, 0, 0, fill=color, width=3, arrow=tk.LAST, arrowshape=(10, 12, 4))
            
            self.robot_markers[name] = (circle, text, arrow, color)
    
    def update_robot(self, name, x, y, yaw):
        """Update robot position and orientation."""
        if name not in self.robot_markers:
            self.add_robot(name)
        
        circle, text, arrow, color = self.robot_markers[name]
        
        # Convert to canvas coordinates
        canvas_x = self._map_to_canvas_x(x)
        canvas_y = self._map_to_canvas_y(y)
        
        # Update circle position
        self.coords(circle, canvas_x - 10, canvas_y - 10, canvas_x + 10, canvas_y + 10)
        
        # Update text position (above robot)
        self.coords(text, canvas_x, canvas_y - 20)
        
        # Update arrow (direction indicator)
        arrow_length = 25
        end_x = canvas_x + arrow_length * math.cos(yaw)
        end_y = canvas_y - arrow_length * math.sin(yaw)  # Negative because canvas Y is inverted
        self.coords(arrow, canvas_x, canvas_y, end_x, end_y)


class JoystickWidget(tk.Canvas):
    """Joystick widget for controlling robot."""
    
    def __init__(self, parent, size=250, callback=None, **kwargs):
        super().__init__(parent, width=size, height=size, bg='#2b2b2b', **kwargs)
        self.size = size
        self.center = size // 2
        self.radius = size // 2 - 20
        self.callback = callback
        
        # Draw outer circle
        self.create_oval(10, 10, size - 10, size - 10, outline='#555', width=2)
        
        # Draw center cross
        self.create_line(self.center, 10, self.center, size - 10, fill='#444', width=1)
        self.create_line(10, self.center, size - 10, self.center, fill='#444', width=1)
        
        # Joystick indicator
        self.indicator = self.create_oval(
            self.center - 15, self.center - 15,
            self.center + 15, self.center + 15,
            fill='#4CAF50', outline='#fff', width=2
        )
        
        # Current position
        self.x = 0.0  # -1 to 1
        self.y = 0.0  # -1 to 1
        
        # Bind events
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<Button-1>', self._on_drag)
    
    def _on_drag(self, event):
        """Handle mouse drag."""
        dx = event.x - self.center
        dy = self.center - event.y  # Invert Y
        
        # Limit to circle
        dist = math.sqrt(dx**2 + dy**2)
        if dist > self.radius:
            dx = dx / dist * self.radius
            dy = dy / dist * self.radius
        
        # Normalize
        self.x = dx / self.radius
        self.y = dy / self.radius
        
        # Update indicator
        canvas_x = self.center + dx
        canvas_y = self.center - dy
        self.coords(self.indicator, canvas_x - 15, canvas_y - 15, canvas_x + 15, canvas_y + 15)
        
        if self.callback:
            self.callback(self.x, self.y)
    
    def _on_release(self, event):
        """Reset to center."""
        self.x = 0.0
        self.y = 0.0
        self.coords(self.indicator, self.center - 15, self.center - 15, self.center + 15, self.center + 15)
        
        if self.callback:
            self.callback(0.0, 0.0)
    
    def get_position(self):
        """Get joystick position."""
        return (self.x, self.y)


class AdvancedTrackingServer:
    """Advanced server with map UI and joystick control."""
    
    def __init__(self, host='0.0.0.0', port=6969):
        self.host = host
        self.port = port
        self.clients = []
        self.clients_lock = threading.Lock()
        self.running = True
        
        # Control parameters
        self.max_speed = 0.5  # m/s
        self.max_angle = 85.0  # deg/s
        
        # Load config and initialize tracker
        print("\n" + "="*70)
        print("[Server] 🚀 STARTING ADVANCED TRACKING SERVER")
        print("="*70)
        print("[Server] Loading configuration from config.json...")
        self.config = load_config()
        robot_config = self.config.get_robot_config()
        
        print(f"\n[Server] 📋 Found {len(robot_config)} robots in config:")
        for name, cfg in robot_config.items():
            print(f"  - {name}: Robot IP={cfg['ip']}, OptiTrack UDP Port={cfg['port']}")
        
        # Initialize tracker
        print(f"\n[Server] 🔧 Initializing OptiTrack tracker...")
        self.tracker = RobotTracker(robot_config)
        self.robots = self.tracker.robots
        print(f"[Server] ✓ Created {len(self.robots)} Robot instances")
        
        # Start tracking
        print(f"\n[Server] 🎯 Starting UDP listeners for OptiTrack data...")
        self.tracker.start()
        print("[Server] ✓ All tracking threads started")
        print("\n[Server] 💡 TIP: Check terminal for UDP packet reception messages")
        print("="*70 + "\n")
        
        # Setup GUI
        self.root = tk.Tk()
        self.root.title("Advanced Robot Control Server with Tracking")
        self.root.configure(bg='#1e1e1e')
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        
        self._setup_ui()
        
        # Start TCP server
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        # Update UI periodically
        self.root.after(100, self._update_ui)
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Title
        title = tk.Label(
            self.root,
            text="🤖 Advanced Robot Control Server",
            font=('Arial', 18, 'bold'),
            bg='#1e1e1e',
            fg='#fff'
        )
        title.pack(pady=10)
        
        # Status bar
        self.status_label = tk.Label(
            self.root,
            text=f"Server: {self.host}:{self.port} | Clients: 0 | Robots: {len(self.robots)}",
            font=('Arial', 11),
            bg='#1e1e1e',
            fg='#4CAF50'
        )
        self.status_label.pack(pady=5)
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(padx=15, pady=10)
        
        # Left side - Map
        left_panel = tk.Frame(main_frame, bg='#1e1e1e')
        left_panel.pack(side=tk.LEFT, padx=10)
        
        map_label = tk.Label(
            left_panel,
            text="Robot Positions (OptiTrack)",
            font=('Arial', 13, 'bold'),
            bg='#1e1e1e',
            fg='#fff'
        )
        map_label.pack(pady=5)
        
        self.map_widget = MapWidget(left_panel, width=600, height=600)
        self.map_widget.pack(pady=5)
        
        # Add robots to map
        for name in self.robots.keys():
            self.map_widget.add_robot(name)
        
        # Position text display below map
        pos_text_frame = tk.Frame(left_panel, bg='#1e1e1e')
        pos_text_frame.pack(pady=10, fill=tk.BOTH)
        
        pos_title = tk.Label(
            pos_text_frame,
            text="Robot Positions (Text)",
            font=('Arial', 11, 'bold'),
            bg='#1e1e1e',
            fg='#fff'
        )
        pos_title.pack(pady=5)
        
        # Create text widget for positions
        text_bg = '#2b2b2b'
        self.position_text = tk.Text(
            pos_text_frame,
            height=8,
            width=60,
            bg=text_bg,
            fg='#00ff00',
            font=('Courier', 10),
            relief=tk.FLAT,
            state=tk.DISABLED
        )
        self.position_text.pack(pady=5, padx=5)
        
        # Right side - Controls
        right_panel = tk.Frame(main_frame, bg='#1e1e1e')
        right_panel.pack(side=tk.LEFT, padx=10, fill=tk.BOTH)
        
        # Speed control
        speed_frame = tk.Frame(right_panel, bg='#1e1e1e')
        speed_frame.pack(pady=10)
        
        speed_label = tk.Label(
            speed_frame,
            text="Speed Control",
            font=('Arial', 12, 'bold'),
            bg='#1e1e1e',
            fg='#fff'
        )
        speed_label.pack(pady=5)
        
        self.speed_var = tk.DoubleVar(value=0.0)
        speed_slider = tk.Scale(
            speed_frame,
            from_=self.max_speed,
            to=0.0,
            resolution=0.01,
            orient=tk.VERTICAL,
            length=250,
            variable=self.speed_var,
            bg='#333',
            fg='#fff',
            troughcolor='#555',
            highlightthickness=0
        )
        speed_slider.pack(pady=5)
        
        self.speed_display = tk.Label(
            speed_frame,
            text="0.00 m/s",
            font=('Arial', 11),
            bg='#1e1e1e',
            fg='#4CAF50'
        )
        self.speed_display.pack(pady=5)
        
        # Joystick
        joystick_frame = tk.Frame(right_panel, bg='#1e1e1e')
        joystick_frame.pack(pady=10)
        
        joystick_label = tk.Label(
            joystick_frame,
            text="Direction & Turning",
            font=('Arial', 12, 'bold'),
            bg='#1e1e1e',
            fg='#fff'
        )
        joystick_label.pack(pady=5)
        
        self.joystick = JoystickWidget(joystick_frame, size=250)
        self.joystick.pack(pady=5)
        
        joystick_info = tk.Label(
            joystick_frame,
            text="UP=Forward | LEFT/RIGHT=Turn",
            font=('Arial', 9),
            bg='#1e1e1e',
            fg='#888'
        )
        joystick_info.pack(pady=5)
        
        # Command display
        self.cmd_display = tk.Label(
            right_panel,
            text="Command: direction=0, angle=0.0°/s",
            font=('Arial', 11, 'bold'),
            bg='#1e1e1e',
            fg='#FFA500'
        )
        self.cmd_display.pack(pady=10)
        
        # Buttons
        button_frame = tk.Frame(right_panel, bg='#1e1e1e')
        button_frame.pack(pady=10)
        
        stop_btn = tk.Button(
            button_frame,
            text="EMERGENCY STOP",
            font=('Arial', 11, 'bold'),
            bg='#f44336',
            fg='#fff',
            command=self._emergency_stop,
            padx=15,
            pady=8
        )
        stop_btn.pack(pady=5)
        
        quit_btn = tk.Button(
            button_frame,
            text="Quit Server",
            font=('Arial', 11),
            bg='#555',
            fg='#fff',
            command=self.shutdown,
            padx=15,
            pady=8
        )
        quit_btn.pack(pady=5)
    
    def _update_ui(self):
        """Update UI periodically."""
        if not self.running:
            return
        
        # Update robot positions on map and collect text
        position_lines = []
        position_lines.append("=" * 70)
        position_lines.append(f"{'Robot':<12} {'X (m)':<10} {'Y (m)':<10} {'Yaw (rad)':<12} {'Yaw (°)':<10}")
        position_lines.append("-" * 70)
        
        for name, robot in self.robots.items():
            x, y, yaw = robot.get_position()
            self.map_widget.update_robot(name, x, y, yaw)
            
            # Add to text display
            yaw_deg = yaw * 180.0 / 3.14159
            position_lines.append(f"{name:<12} {x:<10.4f} {y:<10.4f} {yaw:<12.4f} {yaw_deg:<10.2f}")
        
        position_lines.append("=" * 70)
        
        # Update position text widget
        self.position_text.config(state=tk.NORMAL)
        self.position_text.delete(1.0, tk.END)
        self.position_text.insert(1.0, "\n".join(position_lines))
        self.position_text.config(state=tk.DISABLED)
        
        # Update speed display
        speed = self.speed_var.get()
        self.speed_display.config(text=f"{speed:.2f} m/s")
        
        # Get joystick position
        joy_x, joy_y = self.joystick.get_position()
        
        # Compute command
        if speed > 0.01 and joy_y > 0.1:
            direction = 1
        else:
            direction = 0
        
        # Invert X so positive joystick = turn right, negative = turn left
        angle = -joy_x * self.max_angle
        
        # Update command display
        self.cmd_display.config(text=f"Command: direction={direction}, angle={angle:.1f}°/s")
        
        # Broadcast command
        self.broadcast_command(direction, angle)
        
        # Update status
        with self.clients_lock:
            client_count = len(self.clients)
        self.status_label.config(
            text=f"Server: {self.host}:{self.port} | Clients: {client_count} | Robots: {len(self.robots)}"
        )
        
        # Schedule next update
        self.root.after(100, self._update_ui)
    
    def _emergency_stop(self):
        """Emergency stop."""
        self.speed_var.set(0.0)
        self.broadcast_command(0, 0.0)
        print("[Server] EMERGENCY STOP")
    
    def broadcast_command(self, direction, angle):
        """Broadcast command to all clients."""
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
        """Handle client connection."""
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
            print(f"[Server] ✓ TCP Server: {self.host}:{self.port}")
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
        """Shutdown server."""
        print("\n[Server] Shutting down...")
        self.running = False
        
        # Close clients
        with self.clients_lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
        
        # Stop tracking
        self.tracker.stop()
        
        self.root.quit()
    
    def run(self):
        """Run the server."""
        print("[Server] UI Server started")
        self.root.mainloop()


def main():
    """Main entry point."""
    port = 6969
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)
    
    server = AdvancedTrackingServer(host='0.0.0.0', port=port)
    server.run()


if __name__ == '__main__':
    main()

