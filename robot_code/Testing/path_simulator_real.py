#!/usr/bin/env python3
"""
Real Robot Path Simulator with UI
Draw paths and control real tracked robots using the PathFollower module.
"""

import tkinter as tk
import math
import time
import socket
import json
import sys
from pathlib import Path
import threading

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.core.config_loader import load_config
from src.optitrack.tracker import RobotTracker
from path_follower import PathFollower


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
                    # Close existing connection if any
                    if self.client_socket:
                        try:
                            self.client_socket.close()
                        except:
                            pass
                    
                    self.client_socket = client_socket
                    self.connected = True
                    print(f"[Controller] ✓ Robot connected from {address}")
                
                # Keep connection alive
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
                
                # Connection lost
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
    
    def send_command(self, direction, angle):
        """Send command to robot."""
        with self.clients_lock:
            if not self.connected or not self.client_socket:
                return False
            try:
                cmd = {"direction": direction, "angle": -angle}
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


class PathSimulatorReal:
    """UI for real robot path control."""
    
    def __init__(self, robot_name='umh_5'):
        self.root = tk.Tk()
        self.root.title(f"🤖 Real Robot Controller - {robot_name}")
        self.root.configure(bg='#1e1e1e')
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        
        self.canvas_width = 600
        self.canvas_height = 600
        self.scale = 100
        
        self.path_points = []
        self.robot_name = robot_name
        
        # Load config
        print(f"\n[Controller] Loading configuration...")
        self.config = load_config()
        robot_config = self.config.get_robot_config()
        
        if robot_name not in robot_config:
            print(f"[Controller] ✗ Robot '{robot_name}' not found!")
            sys.exit(1)
        
        self.robot_ip = robot_config[robot_name]['ip']
        
        # Initialize tracker
        print(f"[Controller] Initializing OptiTrack...")
        tracker_config = {robot_name: robot_config[robot_name]}
        self.tracker = RobotTracker(tracker_config)
        self.robot = self.tracker.robots[robot_name]
        
        # Initialize TCP server for robot to connect to
        self.controller = RobotController(host='0.0.0.0', port=6969)
        
        # Path follower
        self.follower = None
        
        # State
        self.is_animating = False
        self.tracking_active = False
        self.last_control_time = None
        self.robot_visual = None
        
        # Settings
        self.use_prediction = True
        self.estimated_delay_ms = 100
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup UI."""
        title = tk.Label(
            self.root, text=f"🤖 Real Robot Controller - {self.robot_name}",
            font=('Arial', 18, 'bold'), bg='#1e1e1e', fg='#fff'
        )
        title.pack(pady=8)
        
        # Settings
        settings_frame = tk.Frame(self.root, bg='#1e1e1e')
        settings_frame.pack(pady=5)
        
        tk.Label(settings_frame, text="Delay:", bg='#1e1e1e', fg='#fff', 
                font=('Arial', 9)).pack(side=tk.LEFT, padx=5)
        self.delay_var = tk.IntVar(value=self.estimated_delay_ms)
        delay_slider = tk.Scale(
            settings_frame, from_=0, to=300, orient=tk.HORIZONTAL,
            variable=self.delay_var, bg='#333', fg='#fff',
            highlightthickness=0, command=self._on_delay_change, length=100
        )
        delay_slider.pack(side=tk.LEFT, padx=5)
        self.delay_label = tk.Label(settings_frame, text=f"{self.estimated_delay_ms}ms",
                                     bg='#1e1e1e', fg='#4CAF50', font=('Arial', 9, 'bold'))
        self.delay_label.pack(side=tk.LEFT, padx=5)
        
        self.prediction_var = tk.BooleanVar(value=self.use_prediction)
        prediction_check = tk.Checkbutton(
            settings_frame, text="Prediction", variable=self.prediction_var,
            bg='#1e1e1e', fg='#fff', selectcolor='#333', font=('Arial', 9),
            command=self._on_setting_change
        )
        prediction_check.pack(side=tk.LEFT, padx=10)
        
        self.status_label = tk.Label(
            self.root, text="Not connected", font=('Arial', 10),
            bg='#1e1e1e', fg='#FFA500'
        )
        self.status_label.pack(pady=3)
        
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(padx=20, pady=8)
        
        self.canvas = tk.Canvas(
            main_frame, width=self.canvas_width, height=self.canvas_height,
            bg='#2b2b2b', highlightthickness=2, highlightbackground='#555'
        )
        self.canvas.pack()
        
        self._draw_grid()
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        
        control_frame = tk.Frame(self.root, bg='#1e1e1e')
        control_frame.pack(pady=8)
        
        self.cmd_label = tk.Label(
            control_frame, text="Ready", font=('Arial', 10, 'bold'),
            bg='#1e1e1e', fg='#888'
        )
        self.cmd_label.pack(pady=3)
        
        button_frame = tk.Frame(control_frame, bg='#1e1e1e')
        button_frame.pack(pady=5)
        
        self.connect_btn = tk.Button(
            button_frame, text="🔌 Connect", font=('Arial', 10, 'bold'),
            bg='#2196F3', fg='#fff', command=self._connect,
            padx=12, pady=6
        )
        self.connect_btn.pack(side=tk.LEFT, padx=3)
        
        self.start_btn = tk.Button(
            button_frame, text="▶ Start", font=('Arial', 10, 'bold'),
            bg='#4CAF50', fg='#fff', command=self._start,
            padx=12, pady=6, state=tk.DISABLED
        )
        self.start_btn.pack(side=tk.LEFT, padx=3)
        
        self.stop_btn = tk.Button(
            button_frame, text="⏸ Stop", font=('Arial', 10, 'bold'),
            bg='#FFA500', fg='#fff', command=self._stop,
            padx=12, pady=6, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=3)
        
        self.emergency_btn = tk.Button(
            button_frame, text="🛑 STOP", font=('Arial', 10, 'bold'),
            bg='#f44336', fg='#fff', command=self._emergency,
            padx=12, pady=6, state=tk.DISABLED
        )
        self.emergency_btn.pack(side=tk.LEFT, padx=3)
        
        self.clear_btn = tk.Button(
            button_frame, text="🗑 Clear", font=('Arial', 10),
            bg='#555', fg='#fff', command=self._clear,
            padx=12, pady=6
        )
        self.clear_btn.pack(side=tk.LEFT, padx=3)
        
        info_frame = tk.Frame(self.root, bg='#1e1e1e')
        info_frame.pack(pady=5)
        
        self.info_label = tk.Label(
            info_frame, text="Not tracking",
            font=('Arial', 9), bg='#1e1e1e', fg='#888'
        )
        self.info_label.pack()
        
        # Debug panel
        debug_frame = tk.Frame(self.root, bg='#1e1e1e')
        debug_frame.pack(pady=5)
        
        tk.Label(debug_frame, text="Debug Info:", font=('Arial', 9, 'bold'),
                bg='#1e1e1e', fg='#FFA500').pack()
        
        self.debug_label = tk.Label(
            debug_frame, text=self._get_debug_info(),
            font=('Courier', 8), bg='#1e1e1e', fg='#888',
            justify=tk.LEFT
        )
        self.debug_label.pack()
        
    def _draw_grid(self):
        """Draw grid."""
        for i in range(0, self.canvas_width + 1, self.scale):
            self.canvas.create_line(i, 0, i, self.canvas_height, fill='#333', width=1)
            if i % self.scale == 0:
                self.canvas.create_text(i, self.canvas_height - 10,
                                      text=f"{i//self.scale}m", fill='#666', font=('Arial', 8))
        
        for i in range(0, self.canvas_height + 1, self.scale):
            self.canvas.create_line(0, i, self.canvas_width, i, fill='#333', width=1)
            if i % self.scale == 0:
                self.canvas.create_text(10, i, text=f"{i//self.scale}m", fill='#666', font=('Arial', 8))
        
        self.canvas.create_oval(
            self.canvas_width//2 - 5, self.canvas_height//2 - 5,
            self.canvas_width//2 + 5, self.canvas_height//2 + 5,
            fill='#FF5722', outline='#fff', tags='origin'
        )
    
    def _world_to_canvas(self, x_m, y_m):
        """Convert meters to canvas pixels."""
        x = x_m * self.scale + self.canvas_width / 2
        y = y_m * self.scale + self.canvas_height / 2
        return x, y
    
    def _canvas_to_world(self, x, y):
        """Convert canvas pixels to meters."""
        x_m = (x - self.canvas_width / 2) / self.scale
        y_m = (y - self.canvas_height / 2) / self.scale
        return x_m, y_m
    
    def _on_canvas_click(self, event):
        """Add waypoint."""
        if self.is_animating or not self.tracking_active:
            return
        
        x, y = event.x, event.y
        self.path_points.append((x, y))
        
        self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                               fill='#4CAF50', outline='#fff', tags='waypoint')
        self.canvas.create_text(x, y - 15, text=str(len(self.path_points)),
                               fill='#4CAF50', font=('Arial', 10, 'bold'), tags='waypoint')
        
        if len(self.path_points) > 1:
            prev_x, prev_y = self.path_points[-2]
            self.canvas.create_line(prev_x, prev_y, x, y, fill='#4CAF50', width=2, tags='path_line')
        
        self.cmd_label.config(text=f"Waypoints: {len(self.path_points)}")
        self.start_btn.config(state=tk.NORMAL if len(self.path_points) > 0 else tk.DISABLED)
    
    def _draw_robot(self):
        """Draw robot."""
        if self.robot_visual:
            self.canvas.delete(self.robot_visual)
            self.canvas.delete('robot_arrow')
            self.canvas.delete('predicted_pos')
        
        x_m, y_m, yaw = self.robot.get_position()
        x, y = self._world_to_canvas(x_m, y_m)
        
        size = 20
        self.robot_visual = self.canvas.create_oval(
            x - size, y - size, x + size, y + size,
            fill='#2196F3', outline='#fff', width=2
        )
        
        arrow_len = size * 1.5
        arrow_x = x + arrow_len * math.cos(yaw)
        arrow_y = y + arrow_len * math.sin(yaw)
        self.canvas.create_line(x, y, arrow_x, arrow_y,
                               fill='#fff', width=3, arrow=tk.LAST, tags='robot_arrow')
        
        # Draw predicted position if follower exists
        if self.follower and hasattr(self.follower, 'predictor') and self.use_prediction:
            pred_x_m, pred_y_m, pred_yaw = self.follower.predictor.predict(
                x_m, y_m, yaw, self.estimated_delay_ms / 1000.0
            )
            pred_x, pred_y = self._world_to_canvas(pred_x_m, pred_y_m)
            
            # Draw predicted position
            pred_size = size * 0.7
            self.canvas.create_oval(
                pred_x - pred_size, pred_y - pred_size,
                pred_x + pred_size, pred_y + pred_size,
                fill='', outline='#FFA500', width=2, dash=(4, 4),
                tags='predicted_pos'
            )
            
            # Draw predicted arrow
            pred_arrow_x = pred_x + arrow_len * 0.7 * math.cos(pred_yaw)
            pred_arrow_y = pred_y + arrow_len * 0.7 * math.sin(pred_yaw)
            self.canvas.create_line(
                pred_x, pred_y, pred_arrow_x, pred_arrow_y,
                fill='#FFA500', width=2, arrow=tk.LAST, tags='predicted_pos'
            )
    
    def _on_delay_change(self, value):
        """Handle delay change."""
        self.estimated_delay_ms = int(value)
        self.delay_label.config(text=f"{self.estimated_delay_ms}ms")
        if self.follower:
            self.follower.estimated_delay_ms = self.estimated_delay_ms
    
    def _on_setting_change(self):
        """Handle setting change."""
        self.use_prediction = self.prediction_var.get()
        if self.follower:
            self.follower.use_prediction = self.use_prediction
    
    def _connect(self):
        """Start server and tracking."""
        self.status_label.config(text="Starting server...", fg='#FFA500')
        self.connect_btn.config(state=tk.DISABLED)
        self.root.update()
        
        # Start TCP server
        print("[Controller] Starting TCP server...")
        self.controller.start_server()
        time.sleep(0.5)
        
        # Start OptiTrack tracking
        print("[Controller] Starting OptiTrack tracking...")
        self.tracker.start()
        time.sleep(1)
        
        self.tracking_active = True
        self.status_label.config(text=f"✓ Server running - Waiting for {self.robot_name}", fg='#4CAF50')
        self.connect_btn.config(text="✓ Server Running", state=tk.DISABLED)
        self.emergency_btn.config(state=tk.NORMAL)
        
        # Start position update loop
        self._update_position()
        
        # Start connection status check
        self._check_connection_status()
    
    def _check_connection_status(self):
        """Check robot TCP connection status."""
        if not self.tracking_active:
            return
        
        if self.controller.connected:
            self.status_label.config(
                text=f"✓ Server running - {self.robot_name} connected",
                fg='#4CAF50'
            )
        else:
            self.status_label.config(
                text=f"✓ Server running - Waiting for {self.robot_name}",
                fg='#FFA500'
            )
        
        self.root.after(500, self._check_connection_status)
    
    def _update_position(self):
        """Update robot position display."""
        if not self.tracking_active:
            return
        
        x, y, yaw = self.robot.get_position()
        self._draw_robot()
        
        yaw_deg = math.degrees(yaw)
        self.info_label.config(
            text=f"Position: ({x:.3f}m, {y:.3f}m) | Heading: {yaw_deg:.1f}°"
        )
        self.debug_label.config(text=self._get_debug_info())
        
        self.root.after(50, self._update_position)
    
    def _get_debug_info(self):
        """Get debug information."""
        if not self.tracking_active:
            return "Not connected"
        
        x, y, yaw = self.robot.get_position()
        yaw_deg = math.degrees(yaw)
        
        lines = [
            f"Current Location:  ({x:6.3f}m, {y:6.3f}m)",
            f"Current Rotation:  {yaw_deg:7.2f}°"
        ]
        
        if self.follower and hasattr(self.follower, 'predictor'):
            pred_x, pred_y, pred_yaw = self.follower.predictor.predict(
                x, y, yaw, self.estimated_delay_ms / 1000.0
            )
            pred_yaw_deg = math.degrees(pred_yaw)
            lines.append(f"Predicted Location: ({pred_x:6.3f}m, {pred_y:6.3f}m)")
            lines.append(f"Predicted Rotation: {pred_yaw_deg:7.2f}°")
            
            # Show calculated orientation from follower
            state = self.follower.get_state()
            if state['angle_to_target'] is not None:
                target_angle_deg = math.degrees(state['angle_to_target'])
                lines.append(f"Target Angle Error: {target_angle_deg:7.2f}°")
        else:
            lines.append("Predicted Location: N/A")
            lines.append("Predicted Rotation: N/A")
            lines.append("Target Angle Error: N/A")
        
        return "\n".join(lines)
    
    def _start(self):
        """Start path following."""
        if len(self.path_points) == 0 or not self.controller.connected:
            return
        
        # Convert waypoints to meters
        waypoints_meters = [self._canvas_to_world(x, y) for x, y in self.path_points]
        
        # Create follower
        self.follower = PathFollower(
            waypoints=waypoints_meters,
            waypoint_tolerance=0.15,
            use_prediction=self.use_prediction,
            estimated_delay_ms=self.estimated_delay_ms
        )
        
        self.is_animating = True
        self.last_control_time = time.time()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.DISABLED)
        self.cmd_label.config(text="Moving...", fg='#4CAF50')
        
        self._control_loop()
    
    def _control_loop(self):
        """Control loop."""
        if not self.is_animating:
            return
        
        current_time = time.time()
        control_dt = current_time - self.last_control_time
        
        # 10Hz control
        if control_dt < 0.1:
            self.root.after(10, self._control_loop)
            return
        
        self.last_control_time = current_time
        
        if self.follower.is_complete():
            self._stop()
            self.cmd_label.config(text="✓ Complete!", fg='#4CAF50')
            self.controller.send_command(0, 0.0)
            return
        
        # Get position and compute command
        x, y, yaw = self.robot.get_position()
        self.follower.update_position(x, y, yaw)
        direction, turn_rate = self.follower.compute_command()
        
        # Send command (invert angle sign: robot expects positive = left turn)
        self.controller.send_command(direction, -turn_rate)
        
        # Update status
        state = self.follower.get_state()
        self.cmd_label.config(
            text=f"Waypoint {state['waypoint_index']+1}/{state['total_waypoints']}"
        )
        
        self.root.after(10, self._control_loop)
    
    def _stop(self):
        """Stop."""
        self.is_animating = False
        
        if self.controller.connected:
            self.controller.send_command(0, 0.0)
        
        # Reset follower predictor to avoid stale velocity data
        if self.follower:
            self.follower.reset()
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.NORMAL)
        self.cmd_label.config(text="Stopped", fg='#FFA500')
    
    def _emergency(self):
        """Emergency stop."""
        self.is_animating = False
        
        if self.controller.connected:
            self.controller.send_command(0, 0.0)
            print("[Controller] EMERGENCY STOP")
        
        # Reset follower predictor
        if self.follower:
            self.follower.reset()
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.cmd_label.config(text="🛑 EMERGENCY", fg='#f44336')
    
    def _clear(self):
        """Clear path."""
        if self.is_animating:
            return
        
        self.path_points = []
        self.follower = None
        
        self.canvas.delete('waypoint')
        self.canvas.delete('path_line')
        
        self.start_btn.config(state=tk.DISABLED)
        self.cmd_label.config(text="Cleared", fg='#888')
    
    def shutdown(self):
        """Shutdown."""
        print("\n[Controller] Shutting down...")
        
        self.is_animating = False
        
        # Send stop command if connected
        if self.controller.connected:
            self.controller.send_command(0, 0.0)
        
        # Shutdown TCP server
        self.controller.shutdown()
        
        # Stop OptiTrack tracking
        if self.tracking_active:
            self.tracker.stop()
        
        self.root.quit()
        print("[Controller] Complete")
    
    def run(self):
        """Run."""
        print(f"\n[Controller] Starting for {self.robot_name}")
        print("[Controller] Click 'Connect' to begin\n")
        self.root.mainloop()


def main():
    robot_name = 'umh_5'
    if len(sys.argv) > 1:
        robot_name = sys.argv[1]
    
    try:
        app = PathSimulatorReal(robot_name=robot_name)
        app.run()
    except KeyboardInterrupt:
        print("\n[Controller] Interrupted")
    except Exception as e:
        print(f"[Controller] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
