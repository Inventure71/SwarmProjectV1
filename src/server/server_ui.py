#!/usr/bin/env python3
"""
Advanced UI Server for Robot Control
Features a graphical interface with:
- Speed slider for controlling linear velocity
- Joystick for controlling direction and turning angle
Commands are sent as JSON: {"direction": 0/1, "angle": degrees_per_sec}
"""

import socket
import threading
import json
import sys
import tkinter as tk
from tkinter import ttk
import math

class JoystickWidget(tk.Canvas):
    """Custom joystick widget for controlling robot direction and turn angle."""
    
    def __init__(self, parent, size=300, callback=None, **kwargs):
        super().__init__(parent, width=size, height=size, bg='#2b2b2b', **kwargs)
        self.size = size
        self.center = size // 2
        self.radius = size // 2 - 20
        self.callback = callback
        
        # Draw outer circle
        self.create_oval(
            10, 10, size - 10, size - 10,
            outline='#555', width=2
        )
        
        # Draw center cross
        self.create_line(
            self.center, 10, self.center, size - 10,
            fill='#444', width=1
        )
        self.create_line(
            10, self.center, size - 10, self.center,
            fill='#444', width=1
        )
        
        # Joystick indicator
        self.indicator = self.create_oval(
            self.center - 15, self.center - 15,
            self.center + 15, self.center + 15,
            fill='#4CAF50', outline='#fff', width=2
        )
        
        # Current position
        self.x = 0.0  # normalized -1 to 1 (left to right)
        self.y = 0.0  # normalized -1 to 1 (down to up)
        
        # Bind mouse events
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<Button-1>', self._on_drag)
        
    def _on_drag(self, event):
        """Handle mouse drag."""
        # Convert to normalized coordinates
        dx = event.x - self.center
        dy = self.center - event.y  # Invert y
        
        # Limit to circle
        dist = math.sqrt(dx**2 + dy**2)
        if dist > self.radius:
            dx = dx / dist * self.radius
            dy = dy / dist * self.radius
        
        # Normalize to -1..1
        self.x = dx / self.radius
        self.y = dy / self.radius
        
        # Update indicator position
        canvas_x = self.center + dx
        canvas_y = self.center - dy
        self.coords(
            self.indicator,
            canvas_x - 15, canvas_y - 15,
            canvas_x + 15, canvas_y + 15
        )
        
        if self.callback:
            self.callback(self.x, self.y)
    
    def _on_release(self, event):
        """Reset to center on release."""
        self.x = 0.0
        self.y = 0.0
        self.coords(
            self.indicator,
            self.center - 15, self.center - 15,
            self.center + 15, self.center + 15
        )
        
        if self.callback:
            self.callback(0.0, 0.0)
    
    def get_position(self):
        """Get current joystick position."""
        return (self.x, self.y)


class UIServer:
    def __init__(self, host='0.0.0.0', port=6969):
        self.host = host
        self.port = port
        self.clients = []
        self.clients_lock = threading.Lock()
        self.running = True
        
        # Control state
        self.max_speed = 0.5  # m/s
        self.max_angle = 85.0  # deg/s (approximately 1.5 rad/s)
        self.current_direction = 0
        self.current_angle = 0.0
        
        # Setup GUI
        self.root = tk.Tk()
        self.root.title("Robot Control Server")
        self.root.configure(bg='#1e1e1e')
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        
        self._setup_ui()
        
        # Start server in background
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        # Update command timer
        self.root.after(100, self._update_command)
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Title
        title = tk.Label(
            self.root,
            text="🤖 Robot Control Server",
            font=('Arial', 20, 'bold'),
            bg='#1e1e1e',
            fg='#fff'
        )
        title.pack(pady=10)
        
        # Connection status
        self.status_label = tk.Label(
            self.root,
            text=f"Server: {self.host}:{self.port} | Clients: 0",
            font=('Arial', 12),
            bg='#1e1e1e',
            fg='#4CAF50'
        )
        self.status_label.pack(pady=5)
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(padx=20, pady=10)
        
        # Left panel - Speed control
        left_panel = tk.Frame(main_frame, bg='#1e1e1e')
        left_panel.pack(side=tk.LEFT, padx=10)
        
        speed_label = tk.Label(
            left_panel,
            text="Speed Control",
            font=('Arial', 14, 'bold'),
            bg='#1e1e1e',
            fg='#fff'
        )
        speed_label.pack(pady=10)
        
        # Speed slider (vertical)
        self.speed_var = tk.DoubleVar(value=0.0)
        speed_slider = tk.Scale(
            left_panel,
            from_=self.max_speed,
            to=0.0,
            resolution=0.01,
            orient=tk.VERTICAL,
            length=300,
            variable=self.speed_var,
            bg='#333',
            fg='#fff',
            troughcolor='#555',
            highlightthickness=0,
            command=self._on_speed_change
        )
        speed_slider.pack(pady=5)
        
        self.speed_display = tk.Label(
            left_panel,
            text="0.00 m/s",
            font=('Arial', 12),
            bg='#1e1e1e',
            fg='#4CAF50'
        )
        self.speed_display.pack(pady=5)
        
        # Right panel - Joystick
        right_panel = tk.Frame(main_frame, bg='#1e1e1e')
        right_panel.pack(side=tk.LEFT, padx=10)
        
        joystick_label = tk.Label(
            right_panel,
            text="Direction & Turning",
            font=('Arial', 14, 'bold'),
            bg='#1e1e1e',
            fg='#fff'
        )
        joystick_label.pack(pady=10)
        
        self.joystick = JoystickWidget(
            right_panel,
            size=300,
            callback=self._on_joystick_move
        )
        self.joystick.pack(pady=5)
        
        joystick_info = tk.Label(
            right_panel,
            text="UP = Forward | LEFT/RIGHT = Turn",
            font=('Arial', 10),
            bg='#1e1e1e',
            fg='#888'
        )
        joystick_info.pack(pady=5)
        
        # Command display
        self.cmd_display = tk.Label(
            self.root,
            text="Command: direction=0, angle=0.0°/s",
            font=('Arial', 12, 'bold'),
            bg='#1e1e1e',
            fg='#FFA500'
        )
        self.cmd_display.pack(pady=10)
        
        # Control buttons
        button_frame = tk.Frame(self.root, bg='#1e1e1e')
        button_frame.pack(pady=10)
        
        stop_btn = tk.Button(
            button_frame,
            text="EMERGENCY STOP",
            font=('Arial', 12, 'bold'),
            bg='#f44336',
            fg='#fff',
            command=self._emergency_stop,
            padx=20,
            pady=10
        )
        stop_btn.pack(side=tk.LEFT, padx=5)
        
        quit_btn = tk.Button(
            button_frame,
            text="Quit Server",
            font=('Arial', 12),
            bg='#555',
            fg='#fff',
            command=self.shutdown,
            padx=20,
            pady=10
        )
        quit_btn.pack(side=tk.LEFT, padx=5)
    
    def _on_speed_change(self, value):
        """Handle speed slider change."""
        speed = float(value)
        self.speed_display.config(text=f"{speed:.2f} m/s")
    
    def _on_joystick_move(self, x, y):
        """Handle joystick movement."""
        # x: -1 (left) to 1 (right) -> turn angle
        # y: -1 (back) to 1 (forward) -> direction
        pass  # Command will be computed in _update_command
    
    def _update_command(self):
        """Periodically update and send command based on UI state."""
        if not self.running:
            return
        
        # Get joystick position
        x, y = self.joystick.get_position()
        
        # Get speed
        speed = self.speed_var.get()
        
        # Compute direction: if speed > 0 and joystick pushed up (y > 0), direction = 1
        if speed > 0.01 and y > 0.1:
            direction = 1
        else:
            direction = 0
        
        # Compute angle: x controls turn rate (positive = right, negative = left)
        angle = -x * self.max_angle
        
        # Update command
        self.current_direction = direction
        self.current_angle = angle
        
        # Update display
        self.cmd_display.config(
            text=f"Command: direction={direction}, angle={angle:.1f}°/s"
        )
        
        # Broadcast to clients
        self.broadcast_command(direction, angle)
        
        # Update client count
        with self.clients_lock:
            count = len(self.clients)
        self.status_label.config(
            text=f"Server: {self.host}:{self.port} | Clients: {count}"
        )
        
        # Schedule next update
        self.root.after(100, self._update_command)
    
    def _emergency_stop(self):
        """Send emergency stop command."""
        self.speed_var.set(0.0)
        self.current_direction = 0
        self.current_angle = 0.0
        self.broadcast_command(0, 0.0)
        print("[SERVER] Emergency stop sent!")
    
    def handle_client(self, client_socket, address):
        """Handle a connected client."""
        print(f"[SERVER] Client connected from {address}")
        with self.clients_lock:
            self.clients.append(client_socket)
        
        try:
            while self.running:
                # Keep connection alive, just wait
                client_socket.settimeout(1.0)
                try:
                    data = client_socket.recv(1)
                    if not data:
                        break
                except socket.timeout:
                    continue
        except Exception as e:
            print(f"[SERVER] Client {address} error: {e}")
        finally:
            with self.clients_lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
            client_socket.close()
            print(f"[SERVER] Client {address} disconnected")
    
    def broadcast_command(self, direction, angle):
        """Send command to all connected clients."""
        cmd = {"direction": direction, "angle": angle}
        msg = json.dumps(cmd) + '\n'
        
        with self.clients_lock:
            dead_clients = []
            for client in self.clients:
                try:
                    client.sendall(msg.encode('utf-8'))
                except Exception:
                    dead_clients.append(client)
            
            # Remove dead clients
            for client in dead_clients:
                self.clients.remove(client)
                try:
                    client.close()
                except:
                    pass
    
    def _run_server(self):
        """Run the TCP server to accept client connections."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            server_socket.settimeout(1.0)
            print(f"[SERVER] Listening on {self.host}:{self.port}")
        except OSError as e:
            print(f"[SERVER] ERROR: Cannot bind to port {self.port}: {e}")
            print(f"[SERVER] Port {self.port} may already be in use. Try a different port.")
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
                    print(f"[SERVER] Accept error: {e}")
        
        server_socket.close()
        print("[SERVER] Server socket closed")
    
    def shutdown(self):
        """Shutdown the server and close GUI."""
        print("[SERVER] Shutting down...")
        self.running = False
        
        # Close all client connections
        with self.clients_lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
        
        self.root.quit()
    
    def run(self):
        """Start the GUI main loop."""
        print("[SERVER] UI Server started")
        print("[SERVER] Use the GUI to control connected robots")
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
    
    server = UIServer(host='0.0.0.0', port=port)
    server.run()


if __name__ == '__main__':
    main()

