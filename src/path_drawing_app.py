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

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.core.config_loader import load_config
from src.optitrack.tracker import RobotTracker
from src.control import PathFollower, RobotController


class PathDrawingApp:
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
        
        # Drawing mode state
        self.drawing_mode = False
        self.is_drawing = False
        self.last_draw_point = None
        self.draw_sample_distance = 15  # pixels between sampled points
        
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
        
        # Motion parameters (tuned for smoother movement)
        self.waypoint_tolerance = 0.20          # Distance to reach waypoint (m)
        self.turn_in_place_threshold = 80.0     # Only turn in place if > 80° off
        self.proportional_gain = 3.5            # Turn rate gain
        self.max_turn_rate = 85.0               # Max turn rate deg/s (robot max is ~86°/s)
        
        # Speed control based on distance
        self.slow_down_distance = 0.5           # Start slowing at this distance (m)
        self.min_speed_ratio = 0.4              # Minimum speed when very close (40%)
        
        # Look-ahead parameters
        self.look_ahead_distance = 0.4          # Distance at which to start blending next waypoint
        self.last_direction_command = 1         # Track last command for smooth speed control
        self.move_counter = 0                   # Counter for duty cycle speed control
        
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
        
        # Drawing mode toggle
        self.draw_mode_btn = tk.Button(
            settings_frame, text="✏️ Draw Mode", font=('Arial', 9),
            bg='#555', fg='#fff', command=self._toggle_draw_mode,
            padx=10, pady=4
        )
        self.draw_mode_btn.pack(side=tk.LEFT, padx=10)
        
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
        self.canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_canvas_release)
        
        control_frame = tk.Frame(self.root, bg='#1e1e1e')
        control_frame.pack(pady=8)
        
        self.cmd_label = tk.Label(
            control_frame, text="Click to add waypoints or use Draw Mode", 
            font=('Arial', 10, 'bold'),
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
    
    def _toggle_draw_mode(self):
        """Toggle between click and draw modes."""
        self.drawing_mode = not self.drawing_mode
        if self.drawing_mode:
            self.draw_mode_btn.config(bg='#4CAF50', text="✏️ Drawing ON")
            self.cmd_label.config(text="Draw mode: Drag to draw path", fg='#4CAF50')
            self.canvas.config(cursor="pencil")
        else:
            self.draw_mode_btn.config(bg='#555', text="✏️ Draw Mode")
            self.cmd_label.config(text="Click mode: Click to add waypoints", fg='#888')
            self.canvas.config(cursor="")
    
    def _on_canvas_click(self, event):
        """Handle canvas click - add waypoint in click mode, start drawing in draw mode."""
        if self.is_animating or not self.tracking_active:
            return
        
        x, y = event.x, event.y
        
        if self.drawing_mode:
            # Start drawing
            self.is_drawing = True
            self.last_draw_point = (x, y)
            self._add_waypoint(x, y)
        else:
            # Click mode - add single waypoint
            self._add_waypoint(x, y)
    
    def _on_canvas_drag(self, event):
        """Handle canvas drag - add waypoints while drawing."""
        if not self.drawing_mode or not self.is_drawing:
            return
        
        if self.is_animating or not self.tracking_active:
            return
        
        x, y = event.x, event.y
        
        # Only add point if far enough from last point
        if self.last_draw_point is not None:
            dx = x - self.last_draw_point[0]
            dy = y - self.last_draw_point[1]
            dist = math.sqrt(dx**2 + dy**2)
            
            if dist >= self.draw_sample_distance:
                self._add_waypoint(x, y)
                self.last_draw_point = (x, y)
    
    def _on_canvas_release(self, event):
        """Handle mouse release - stop drawing."""
        if self.drawing_mode:
            self.is_drawing = False
            self.last_draw_point = None
    
    def _add_waypoint(self, x, y):
        """Add a waypoint at the given canvas coordinates."""
        self.path_points.append((x, y))
        
        # Draw waypoint marker (smaller in draw mode)
        if self.drawing_mode:
            size = 3
            self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                   fill='#4CAF50', outline='#4CAF50', tags='waypoint')
        else:
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                                   fill='#4CAF50', outline='#fff', tags='waypoint')
            self.canvas.create_text(x, y - 15, text=str(len(self.path_points)),
                                   fill='#4CAF50', font=('Arial', 10, 'bold'), tags='waypoint')
        
        # Draw line to previous point
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
        
        # Create follower with tuned parameters
        self.follower = PathFollower(
            waypoints=waypoints_meters,
            waypoint_tolerance=self.waypoint_tolerance,
            turn_in_place_threshold=self.turn_in_place_threshold,
            proportional_gain=self.proportional_gain,
            max_turn_rate=self.max_turn_rate,
            use_prediction=self.use_prediction,
            estimated_delay_ms=self.estimated_delay_ms
        )
        
        self.is_animating = True
        self.last_control_time = time.time()
        self.move_counter = 0  # Reset speed control counter
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.DISABLED)
        self.cmd_label.config(text="Moving...", fg='#4CAF50')
        
        self._control_loop()
    
    def _control_loop(self):
        """Control loop with distance-based speed control."""
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
        
        # Calculate distance to current waypoint for speed scaling
        state = self.follower.get_state()
        distance_to_waypoint = state['distance_to_target'] if state['distance_to_target'] is not None else 999
        
        # Implement look-ahead: when close to waypoint, blend direction toward next waypoint
        if direction == 1 and distance_to_waypoint < self.look_ahead_distance:
            current_idx = state['waypoint_index']
            # Check if there's a next waypoint
            if current_idx + 1 < state['total_waypoints']:
                # Get current and next waypoint
                current_target = state['target']
                next_target = self.follower.waypoints[current_idx + 1]
                
                # Calculate angle to next waypoint
                dx_next = next_target[0] - x
                dy_next = next_target[1] - y
                desired_yaw_next = math.atan2(dy_next, dx_next)
                
                # Calculate angle difference to next waypoint
                angle_diff_next = desired_yaw_next - yaw
                while angle_diff_next > math.pi:
                    angle_diff_next -= 2 * math.pi
                while angle_diff_next < -math.pi:
                    angle_diff_next += 2 * math.pi
                angle_diff_next_deg = math.degrees(angle_diff_next)
                
                # Blend between current and next waypoint based on distance
                # Closer to waypoint = more weight on next waypoint
                blend_ratio = 1.0 - (distance_to_waypoint / self.look_ahead_distance)
                blend_ratio = max(0.0, min(1.0, blend_ratio))
                
                # Calculate current angle difference
                angle_diff_current = state['angle_to_target']
                if angle_diff_current is not None:
                    angle_diff_current_deg = math.degrees(angle_diff_current)
                    
                    # Blend the two angles
                    blended_angle_diff = (1.0 - blend_ratio) * angle_diff_current_deg + \
                                        blend_ratio * angle_diff_next_deg
                    
                    # Recalculate turn rate with blended angle
                    turn_rate = max(-self.max_turn_rate,
                                  min(self.max_turn_rate, 
                                      blended_angle_diff * self.proportional_gain))
        
        # Apply distance-based speed control (only very close to waypoint)
        final_direction = direction
        if direction == 1:  # Only apply speed control when moving forward
            # Only slow down when VERY close to the last waypoint
            is_last_waypoint = (state['waypoint_index'] + 1 >= state['total_waypoints'])
            
            if is_last_waypoint and distance_to_waypoint < self.slow_down_distance:
                # Calculate speed ratio based on distance (linear interpolation)
                # Close to waypoint: min_speed_ratio, far: 1.0
                speed_ratio = self.min_speed_ratio + \
                             (1.0 - self.min_speed_ratio) * \
                             (distance_to_waypoint / self.slow_down_distance)
                speed_ratio = max(self.min_speed_ratio, min(1.0, speed_ratio))
                
                # Use counter-based duty cycle for speed control
                # Increment counter and check if we should move this cycle
                self.move_counter += 1
                cycle_length = 10  # 10 control cycles = 1 second
                move_cycles = int(cycle_length * speed_ratio)
                
                if (self.move_counter % cycle_length) >= move_cycles:
                    # Skip this move cycle to slow down
                    final_direction = 0
                    # Keep turning if we're not already turning in place
                    if direction == 1:
                        turn_rate = turn_rate  # Keep the turn rate
            else:
                # Full speed when not the last waypoint or far from waypoint
                self.move_counter = 0  # Reset counter when far
        
        # Send command (angle inverted in send_command at line 106)
        self.controller.send_command(final_direction, -turn_rate)
        
        # Update status
        self.cmd_label.config(
            text=f"Waypoint {state['waypoint_index']+1}/{state['total_waypoints']} | "
                 f"Dist: {distance_to_waypoint:.2f}m"
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
        
        # Reset drawing state
        self.is_drawing = False
        self.last_draw_point = None
        
        self.canvas.delete('waypoint')
        self.canvas.delete('path_line')
        
        self.start_btn.config(state=tk.DISABLED)
        if self.drawing_mode:
            self.cmd_label.config(text="Draw mode: Drag to draw path", fg='#4CAF50')
        else:
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
        app = PathDrawingApp(robot_name=robot_name)
        app.run()
    except KeyboardInterrupt:
        print("\n[Controller] Interrupted")
    except Exception as e:
        print(f"[Controller] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
