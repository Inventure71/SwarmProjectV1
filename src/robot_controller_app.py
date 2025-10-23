#!/usr/bin/env python3
"""
Robot Controller Application
Modular robot path controller with modern UI.
"""

import tkinter as tk
import math
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.config_loader import load_config
from src.optitrack.tracker import RobotTracker
from src.control import PathFollower, RobotController
from src.ui.virtual_joystick import VirtualJoystick
from src.ui.components import (
    ModernButton, StatusLabel, ModernFrame, ModernScale, 
    ModernCheckbutton, CanvasGrid
)
from src.services.recording_service import RecordingService
from src.services.path_service import PathService


class RobotControllerApp:
    """Main robot controller application."""
    
    # Mode constants
    MODE_CLICK = "click"
    MODE_DRAW = "draw"
    MODE_RECORD = "record"
    
    def __init__(self, robot_name='umh_5'):
        self.robot_name = robot_name
        self.current_mode = self.MODE_CLICK
        
        # UI dimensions will be calculated dynamically
        self.canvas_width = 1200  # Initial width
        self.canvas_height = 675  # 16:9 ratio
        self.scale = 50  # Will be adjusted based on canvas size
        
        # State
        self.is_animating = False
        self.tracking_active = False
        self.is_drawing = False
        self.last_draw_point = None
        self.draw_sample_distance = 15
        self.robot_visual = None
        self.last_control_time = None
        
        # Initialize components
        self._load_config()
        self._setup_ui()
        self._setup_services()
        
        # Bind window resize event
        self.root.bind('<Configure>', self._on_window_resize)
        
        # Auto-start server and tracking
        self.root.after(500, self._auto_connect)
        
    def _load_config(self):
        """Load configuration and initialize robot systems."""
        print(f"\n[Controller] Loading configuration...")
        self.config = load_config()
        robot_config = self.config.get_robot_config()
        
        if self.robot_name not in robot_config:
            print(f"[Controller] ✗ Robot '{self.robot_name}' not found!")
            sys.exit(1)
        
        self.robot_ip = robot_config[self.robot_name]['ip']
        
        # Initialize tracker
        print(f"[Controller] Initializing OptiTrack...")
        tracker_config = {self.robot_name: robot_config[self.robot_name]}
        self.tracker = RobotTracker(tracker_config)
        self.robot = self.tracker.robots[self.robot_name]
        
        # Initialize TCP server for robot to connect to
        self.controller = RobotController(host='0.0.0.0', port=6969)
        
        # Path follower
        self.follower = None
        
        # Settings
        self.use_prediction = True
        self.estimated_delay_ms = 100
        
        # Motion parameters
        self.waypoint_tolerance = 0.20
        self.turn_in_place_threshold = 55.0
        self.proportional_gain = 3.5
        self.max_turn_rate = 85.0
        self.slow_down_distance = 0.5
        self.min_speed_ratio = 0.05
        self.curvature_speed_gain = 1.2
        self.look_ahead_distance = 0.4
        self.path_simplification_tolerance = 0.06
        self.min_waypoint_separation = 0.15
        self.segment_pass_distance = 0.09
        self.segment_pass_lateral_factor = 1.7
        self.waypoint_approach_slowdown = 0.45
        self.corner_keep_angle_deg = 22.0
        self.last_throttle_command = 0.0
        
    def _setup_ui(self):
        """Setup the user interface."""
        self.root = tk.Tk()
        self.root.title(f"🤖 Robot Path Controller - {self.robot_name}")
        self.root.configure(bg='#0f0f0f')
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        
        # Title bar
        title_frame = tk.Frame(self.root, bg='#1a1a1a', height=60)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        title = tk.Label(
            title_frame, text=f"🤖 ROBOT PATH CONTROLLER",
            font=('Arial', 20, 'bold'), bg='#1a1a1a', fg='#00ff88'
        )
        title.pack(pady=5)
        
        robot_label = tk.Label(
            title_frame, text=f"Robot: {self.robot_name.upper()}",
            font=('Arial', 11), bg='#1a1a1a', fg='#888'
        )
        robot_label.pack()
        
        # Main container
        main_container = tk.Frame(self.root, bg='#0f0f0f')
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Left panel - Controls
        self._setup_left_panel(main_container)
        
        # Right panel - Canvas
        self._setup_right_panel(main_container)
        
    def _setup_left_panel(self, parent):
        """Setup left control panel."""
        left_panel = tk.Frame(parent, bg='#1a1a1a', width=280)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Mode selector
        self._setup_mode_selector(left_panel)
        
        # Settings
        self._setup_settings(left_panel)
        
        # Status
        self._setup_status(left_panel)
        
        # Controls
        self._setup_controls(left_panel)
        
        # Path management
        self._setup_path_management(left_panel)
        
    def _setup_mode_selector(self, parent):
        """Setup mode selector."""
        mode_frame = ModernFrame(parent, title="🎯 MODE")
        mode_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.mode_buttons = {}
        modes = [
            (self.MODE_CLICK, "📍 Click", "Click to add waypoints"),
            (self.MODE_DRAW, "✏️ Draw", "Drag to draw path"),
            (self.MODE_RECORD, "🎮 Record", "Joystick control & record")
        ]
        
        for mode_id, mode_text, mode_desc in modes:
            btn = ModernButton(
                mode_frame, text=mode_text, style="secondary",
                command=lambda m=mode_id: self._switch_mode(m)
            )
            btn.pack(fill=tk.X, padx=5, pady=3)
            self.mode_buttons[mode_id] = btn
        
        self._update_mode_buttons()
        
    def _setup_settings(self, parent):
        """Setup settings panel."""
        settings_frame = ModernFrame(parent, title="⚙️ SETTINGS")
        settings_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Delay setting
        delay_container = tk.Frame(settings_frame, bg='#1a1a1a')
        delay_container.pack(fill=tk.X, padx=8, pady=5)
        
        tk.Label(delay_container, text="Prediction Delay:", bg='#1a1a1a', fg='#ccc', 
                font=('Arial', 9)).pack(anchor=tk.W)
        
        delay_control = tk.Frame(delay_container, bg='#1a1a1a')
        delay_control.pack(fill=tk.X, pady=3)
        
        self.delay_var = tk.IntVar(value=self.estimated_delay_ms)
        delay_slider = ModernScale(
            delay_control, from_=0, to=300, orient=tk.HORIZONTAL,
            variable=self.delay_var, command=self._on_delay_change
        )
        delay_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.delay_label = tk.Label(delay_control, text=f"{self.estimated_delay_ms}ms",
                                     bg='#1a1a1a', fg='#00ff88', font=('Arial', 9, 'bold'),
                                     width=6)
        self.delay_label.pack(side=tk.LEFT, padx=5)
        
        # Prediction toggle
        self.prediction_var = tk.BooleanVar(value=self.use_prediction)
        prediction_check = ModernCheckbutton(
            settings_frame, text="Enable Position Prediction", 
            variable=self.prediction_var, command=self._on_setting_change
        )
        prediction_check.pack(anchor=tk.W, padx=8, pady=5)
        
    def _setup_status(self, parent):
        """Setup status panel."""
        status_frame = ModernFrame(parent, title="📡 STATUS")
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.status_label = StatusLabel(status_frame, text="⚪ Not Connected", fg='#888')
        self.status_label.pack(fill=tk.X, padx=8, pady=8)
        
    def _setup_controls(self, parent):
        """Setup control buttons."""
        control_frame = ModernFrame(parent, title="🎮 CONTROLS")
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_btn = ModernButton(
            control_frame, text="▶ START PATH", style="success",
            command=self._start, state=tk.DISABLED
        )
        self.start_btn.config(pady=12, font=('Arial', 11, 'bold'))
        self.start_btn.pack(fill=tk.X, padx=5, pady=5)
        
        self.stop_btn = ModernButton(
            control_frame, text="⏸ STOP", style="warning",
            command=self._stop, state=tk.DISABLED
        )
        self.stop_btn.config(pady=12, font=('Arial', 11, 'bold'))
        self.stop_btn.pack(fill=tk.X, padx=5, pady=5)
        
        self.emergency_btn = ModernButton(
            control_frame, text="🛑 EMERGENCY STOP", style="danger",
            command=self._emergency, state=tk.DISABLED
        )
        self.emergency_btn.config(pady=12, font=('Arial', 11, 'bold'))
        self.emergency_btn.pack(fill=tk.X, padx=5, pady=5)
        
    def _setup_path_management(self, parent):
        """Setup path management."""
        path_frame = ModernFrame(parent, title="📁 PATH")
        path_frame.pack(fill=tk.X, padx=10, pady=10)
        
        path_btn_frame = tk.Frame(path_frame, bg='#1a1a1a')
        path_btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.save_btn = ModernButton(
            path_btn_frame, text="💾", style="secondary",
            command=self._save_path, width=4
        )
        self.save_btn.config(font=('Arial', 10, 'bold'))
        self.save_btn.pack(side=tk.LEFT, padx=2)
        
        self.load_btn = ModernButton(
            path_btn_frame, text="📂", style="secondary",
            command=self._load_path, width=4
        )
        self.load_btn.config(font=('Arial', 10, 'bold'))
        self.load_btn.pack(side=tk.LEFT, padx=2)
        
        self.clear_btn = ModernButton(
            path_btn_frame, text="🗑 CLEAR", style="secondary",
            command=self._clear
        )
        self.clear_btn.config(font=('Arial', 10, 'bold'))
        self.clear_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
    def _setup_joystick(self, parent):
        """Setup joystick panel - will be shown in right panel."""
        # Joystick is now set up in _setup_right_panel method
        # This method is kept for compatibility but does nothing
        pass
        
    def _setup_right_panel(self, parent):
        """Setup right panel with canvas and optional joystick."""
        right_container = tk.Frame(parent, bg='#0f0f0f')
        right_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas panel (left side of right container) - save reference for joystick packing
        self.canvas_panel = tk.Frame(right_container, bg='#0f0f0f')
        self.canvas_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Command label
        self.cmd_label = tk.Label(
            self.canvas_panel, text="📍 Click mode: Click to add waypoints", 
            font=('Arial', 11, 'bold'),
            bg='#1a1a1a', fg='#fff', pady=8
        )
        self.cmd_label.pack(fill=tk.X)
        
        # Canvas
        canvas_container = tk.Frame(self.canvas_panel, bg='#1a1a1a', bd=2, relief=tk.GROOVE)
        canvas_container.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.canvas = tk.Canvas(
            canvas_container, width=self.canvas_width, height=self.canvas_height,
            bg='#0a0a0a', highlightthickness=0
        )
        self.canvas.pack(padx=3, pady=3)
        
        # Draw grid
        self.grid_helper = CanvasGrid(self.canvas, self.scale, self.canvas_width, self.canvas_height)
        self.grid_helper.draw_grid()
        
        # Bind events
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        self.canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_canvas_release)
        
        # Info panel
        info_panel = tk.Frame(self.canvas_panel, bg='#1a1a1a', bd=2, relief=tk.GROOVE)
        info_panel.pack(fill=tk.X, pady=(5, 0))
        
        self.info_label = tk.Label(
            info_panel, text="Position: Not tracking",
            font=('Courier', 10), bg='#1a1a1a', fg='#00ff88', pady=8
        )
        self.info_label.pack()
        
        # Debug panel
        debug_panel = tk.Frame(self.canvas_panel, bg='#1a1a1a', bd=2, relief=tk.GROOVE)
        debug_panel.pack(fill=tk.X, pady=(5, 0))
        
        tk.Label(debug_panel, text="📊 DEBUG INFO", font=('Arial', 9, 'bold'),
                bg='#1a1a1a', fg='#00ff88').pack(pady=(5, 0))
        
        self.debug_label = tk.Label(
            debug_panel, text=self._get_debug_info(),
            font=('Courier', 8), bg='#1a1a1a', fg='#ccc',
            justify=tk.LEFT, pady=8
        )
        self.debug_label.pack()
        
        # Joystick panel (right side of right container) - Initially hidden
        self.joystick_container = tk.Frame(right_container, bg='#0f0f0f', width=300)
        
        joystick_frame = tk.LabelFrame(
            self.joystick_container, text="🕹️ JOYSTICK", font=('Arial', 10, 'bold'),
            bg='#1a1a1a', fg='#00ff88', bd=2, relief=tk.GROOVE
        )
        joystick_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.joystick = VirtualJoystick(joystick_frame, size=250)
        self.joystick.pack(padx=15, pady=15)
        
        self.record_btn = ModernButton(
            joystick_frame, text="⏺ START RECORDING", style="danger",
            command=self._toggle_recording
        )
        self.record_btn.config(pady=12, font=('Arial', 11, 'bold'))
        self.record_btn.pack(fill=tk.X, padx=15, pady=(0, 15))
        
    def _setup_services(self):
        """Setup service layer."""
        # Path service
        self.path_service = PathService(
            self.canvas, self._world_to_canvas, self._canvas_to_world
        )
        
        # Recording service
        self.recording_service = RecordingService(
            self.controller, self.tracker, self.robot, self.canvas, self._world_to_canvas
        )
        
        # Set up recording callbacks
        self.recording_service.on_recording_start = self._on_recording_start
        self.recording_service.on_recording_stop = self._on_recording_stop
        self.recording_service.on_position_recorded = self._on_position_recorded
        self.recording_service.set_joystick_enabled(False)
        
    # Coordinate conversion methods
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
    
    # Mode switching
    def _update_mode_buttons(self):
        """Update mode button visual states."""
        for mode_id, btn in self.mode_buttons.items():
            if mode_id == self.current_mode:
                btn.config(bg='#00ff88', fg='#000000', relief=tk.RAISED)
            else:
                btn.config(bg='#2a2a2a', fg='#ffffff', relief=tk.FLAT)
    
    def _switch_mode(self, mode):
        """Switch to a different mode."""
        if self.is_animating:
            from tkinter import messagebox
            messagebox.showwarning("Mode Switch", "Cannot switch modes while path is running!")
            return
        
        # Stop any ongoing recording
        if self.recording_service.is_recording and mode != self.MODE_RECORD:
            self._stop_recording()
        
        self.current_mode = mode
        self._update_mode_buttons()
        
        # Update UI based on mode
        if mode == self.MODE_CLICK:
            self.cmd_label.config(text="📍 Click mode: Click to add waypoints", fg='#fff')
            self.canvas.config(cursor="")
            self.joystick_container.pack_forget()
            # Trigger resize to reclaim joystick space
            self.root.event_generate('<Configure>')
            self.recording_service.set_joystick_enabled(False)
            
        elif mode == self.MODE_DRAW:
            self.cmd_label.config(text="✏️ Draw mode: Drag to draw path", fg='#00aaff')
            self.canvas.config(cursor="pencil")
            self.joystick_container.pack_forget()
            # Trigger resize to reclaim joystick space
            self.root.event_generate('<Configure>')
            self.recording_service.set_joystick_enabled(False)
            
        elif mode == self.MODE_RECORD:
            self.cmd_label.config(text="🎮 Record mode: Use joystick to control robot", fg='#ff6600')
            self.canvas.config(cursor="")
            # Show joystick panel on right side
            self.joystick_container.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0), before=self.canvas_panel)
            self.joystick_container.pack_propagate(False)
            self.root.update()  # Force UI refresh
            # Trigger resize to account for joystick space
            self.root.event_generate('<Configure>')
            self.recording_service.set_joystick_enabled(True)
    
    # Canvas interaction
    def _on_canvas_click(self, event):
        """Handle canvas click."""
        if self.is_animating or not self.tracking_active:
            return
        
        if self.current_mode == self.MODE_RECORD:
            return
        
        x, y = event.x, event.y
        
        if self.current_mode == self.MODE_DRAW:
            self.is_drawing = True
            self.last_draw_point = (x, y)
            self.path_service.add_waypoint(x, y, "draw")
        else:  # MODE_CLICK
            self.path_service.add_waypoint(x, y, "click")
        
        self._update_path_status()
    
    def _on_canvas_drag(self, event):
        """Handle canvas drag."""
        if self.current_mode != self.MODE_DRAW or not self.is_drawing:
            return
        
        if self.is_animating or not self.tracking_active:
            return
        
        x, y = event.x, event.y
        
        if self.last_draw_point is not None:
            dx = x - self.last_draw_point[0]
            dy = y - self.last_draw_point[1]
            dist = math.sqrt(dx**2 + dy**2)
            
            if dist >= self.draw_sample_distance:
                self.path_service.add_waypoint(x, y, "draw")
                self.last_draw_point = (x, y)
                self._update_path_status()
    
    def _on_canvas_release(self, event):
        """Handle mouse release."""
        if self.current_mode == self.MODE_DRAW:
            self.is_drawing = False
            self.last_draw_point = None
    
    def _update_path_status(self):
        """Update path status display."""
        info = self.path_service.get_path_info()
        mode_name = "📍 Click" if self.current_mode == self.MODE_CLICK else "✏️ Draw"
        self.cmd_label.config(text=f"{mode_name} | Waypoints: {info['num_waypoints']}")
        self.start_btn.config(state=tk.NORMAL if info['num_waypoints'] > 0 else tk.DISABLED)
    
    # Recording methods
    def _toggle_recording(self):
        """Toggle motion recording."""
        if not self.tracking_active or not self.controller.connected:
            from tkinter import messagebox
            messagebox.showwarning("Recording", "Please connect to robot first!")
            return
        
        if self.recording_service.is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """Start recording robot motion."""
        self.path_service.clear_path()
        
        if self.recording_service.start_recording():
            self.record_btn.config(text="⏹ STOP RECORDING", style="success")
            self.cmd_label.config(text="🎮 Recording... Use joystick to control robot", fg='#f44336')
            self.start_btn.config(state=tk.DISABLED)
            self.save_btn.config(state=tk.DISABLED)
            self.load_btn.config(state=tk.DISABLED)
            print("[Recording] Started motion recording")
    
    def _stop_recording(self):
        """Stop recording and convert to path."""
        recorded_positions = self.recording_service.stop_recording()
        
        self.record_btn.config(text="⏺ START RECORDING", style="danger")
        self.save_btn.config(state=tk.NORMAL)
        self.load_btn.config(state=tk.NORMAL)
        
        if len(recorded_positions) > 0:
            self.path_service.set_recorded_path(recorded_positions)
            self.cmd_label.config(
                text=f"🎮 Recording complete! Captured {len(recorded_positions)} points",
                fg='#00ff88'
            )
            self.start_btn.config(state=tk.NORMAL)
            print(f"[Recording] Captured {len(recorded_positions)} waypoints")
        else:
            self.cmd_label.config(text="🎮 No motion recorded", fg='#FFA500')
            print("[Recording] No waypoints captured")
    
    def _on_recording_start(self):
        """Callback when recording starts."""
        pass
    
    def _on_recording_stop(self):
        """Callback when recording stops."""
        pass
    
    def _on_position_recorded(self, count):
        """Callback when position is recorded."""
        self.cmd_label.config(text=f"🎮 Recording... {count} points", fg='#f44336')
    
    # Path management
    def _save_path(self):
        """Save current path."""
        self.path_service.save_path(self.robot_name)
    
    def _load_path(self):
        """Load path from file."""
        if self.is_animating:
            from tkinter import messagebox
            messagebox.showwarning("Load Path", "Cannot load path while robot is moving!")
            return
        
        if self.path_service.load_path():
            info = self.path_service.get_path_info()
            self.cmd_label.config(text=f"✓ Loaded {info['num_waypoints']} waypoints", fg='#00ff88')
            self.start_btn.config(state=tk.NORMAL)
    
    def _clear(self):
        """Clear path - works anytime."""
        # Stop path following if active
        if self.is_animating:
            self.is_animating = False
            if self.controller.connected:
                self.controller.send_command(0.0, 0.0)
            if self.follower:
                self.follower.reset()
            self.stop_btn.config(state=tk.DISABLED)
        
        # Stop recording if active
        if self.recording_service.is_recording:
            self._stop_recording()
        
        # Clear path
        self.path_service.clear_path()
        self.is_drawing = False
        self.last_draw_point = None
        
        self.start_btn.config(state=tk.DISABLED)
        
        # Update label based on mode
        if self.current_mode == self.MODE_CLICK:
            self.cmd_label.config(text="📍 Click mode: Click to add waypoints", fg='#fff')
        elif self.current_mode == self.MODE_DRAW:
            self.cmd_label.config(text="✏️ Draw mode: Drag to draw path", fg='#00aaff')
        elif self.current_mode == self.MODE_RECORD:
            self.cmd_label.config(text="🎮 Record mode: Use joystick to control robot", fg='#ff6600')
    
    # Robot control methods
    def _auto_connect(self):
        """Auto-start server and tracking on launch."""
        self._connect()
    
    def _connect(self):
        """Start server and tracking."""
        self.status_label.config(text="🟡 Starting server...", fg='#ffaa00')
        self.root.update()
        
        print("[Controller] Starting TCP server...")
        self.controller.start_server()
        time.sleep(0.5)
        
        print("[Controller] Starting OptiTrack tracking...")
        self.tracker.start()
        time.sleep(1)
        
        self.tracking_active = True
        self.status_label.config(text=f"🟡 Waiting for {self.robot_name.upper()}", fg='#ffaa00')
        self.emergency_btn.config(state=tk.NORMAL)
        
        self._update_position()
        self._check_connection_status()
    
    def _check_connection_status(self):
        """Check robot TCP connection status."""
        if not self.tracking_active:
            return
        
        if self.controller.connected:
            self.status_label.config(text=f"🟢 {self.robot_name.upper()} Connected", fg='#00ff88')
        else:
            self.status_label.config(text=f"🟡 Waiting for {self.robot_name.upper()}", fg='#ffaa00')
        
        self.root.after(500, self._check_connection_status)
    
    def _update_position(self):
        """Update robot position display."""
        if not self.tracking_active:
            return
        
        x, y, yaw = self.robot.get_position()
        self._draw_robot()
        
        yaw_deg = math.degrees(yaw)
        self.info_label.config(text=f"Pos: ({x:6.3f}, {y:6.3f})m | Heading: {yaw_deg:6.1f}°")
        self.debug_label.config(text=self._get_debug_info())
        
        # Process joystick input when joystick control is enabled
        if self.recording_service.joystick_control_active:
            joy_x, joy_y = self.joystick.get_values()
            self.recording_service.process_joystick_input(joy_x, joy_y)
        
        self.root.after(50, self._update_position)
    
    def _draw_robot(self):
        """Draw robot with modern styling."""
        if self.robot_visual:
            self.canvas.delete(self.robot_visual)
            self.canvas.delete('robot_arrow')
            self.canvas.delete('predicted_pos')
        
        x_m, y_m, yaw = self.robot.get_position()
        x, y = self._world_to_canvas(x_m, y_m)
        
        size = 22
        self.robot_visual = self.canvas.create_oval(
            x - size, y - size, x + size, y + size,
            fill='#0066ff', outline='#00aaff', width=3
        )
        
        arrow_len = size * 1.5
        arrow_x = x + arrow_len * math.cos(yaw)
        arrow_y = y + arrow_len * math.sin(yaw)
        self.canvas.create_line(x, y, arrow_x, arrow_y,
                               fill='#fff', width=4, arrow=tk.LAST, tags='robot_arrow')
        
        # Draw predicted position if follower exists
        if self.follower and hasattr(self.follower, 'predictor') and self.use_prediction:
            pred_x_m, pred_y_m, pred_yaw = self.follower.predictor.predict(
                x_m, y_m, yaw, self.estimated_delay_ms / 1000.0
            )
            pred_x, pred_y = self._world_to_canvas(pred_x_m, pred_y_m)
            
            pred_size = size * 0.7
            self.canvas.create_oval(
                pred_x - pred_size, pred_y - pred_size,
                pred_x + pred_size, pred_y + pred_size,
                fill='', outline='#ffaa00', width=3, dash=(5, 3),
                tags='predicted_pos'
            )
            
            pred_arrow_x = pred_x + arrow_len * 0.7 * math.cos(pred_yaw)
            pred_arrow_y = pred_y + arrow_len * 0.7 * math.sin(pred_yaw)
            self.canvas.create_line(
                pred_x, pred_y, pred_arrow_x, pred_arrow_y,
                fill='#ffaa00', width=3, arrow=tk.LAST, tags='predicted_pos'
            )
    
    def _start(self):
        """Start path following."""
        info = self.path_service.get_path_info()
        if info['num_waypoints'] == 0 or not self.controller.connected:
            return
        
        waypoints_meters = info['waypoints_meters']
        
        self.follower = PathFollower(
            waypoints=waypoints_meters,
            waypoint_tolerance=self.waypoint_tolerance,
            turn_in_place_threshold=self.turn_in_place_threshold,
            proportional_gain=self.proportional_gain,
            max_turn_rate=self.max_turn_rate,
            use_prediction=self.use_prediction,
            estimated_delay_ms=self.estimated_delay_ms,
            curvature_speed_gain=self.curvature_speed_gain,
            min_speed_ratio=self.min_speed_ratio,
            slow_down_distance=self.slow_down_distance,
            path_simplification_tolerance=self.path_simplification_tolerance,
            min_waypoint_separation=self.min_waypoint_separation,
            segment_pass_distance=self.segment_pass_distance,
            segment_pass_lateral_factor=self.segment_pass_lateral_factor,
            waypoint_approach_slowdown=self.waypoint_approach_slowdown,
            corner_keep_angle_deg=self.corner_keep_angle_deg
        )
        
        self.is_animating = True
        self.last_control_time = time.time()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.DISABLED)
        self.cmd_label.config(text="▶ Following Path...", fg='#00ff88')
        
        self._control_loop()
    
    def _control_loop(self):
        """Control loop for path following."""
        if not self.is_animating:
            return
        
        current_time = time.time()
        control_dt = current_time - self.last_control_time
        
        if control_dt < 0.1:
            self.root.after(10, self._control_loop)
            return
        
        self.last_control_time = current_time
        
        if self.follower.is_complete():
            self._stop()
            self.cmd_label.config(text="✓ Path Complete!", fg='#00ff88')
            self.controller.send_command(0.0, 0.0)
            return
        
        x, y, yaw = self.robot.get_position()
        self.follower.update_position(x, y, yaw)
        throttle, turn_rate = self.follower.compute_command()
        
        state = self.follower.get_state()
        distance_to_waypoint = state['distance_to_target'] if state['distance_to_target'] is not None else 999
        
        # Apply look-ahead blending
        if throttle > 0.01 and distance_to_waypoint < self.look_ahead_distance:
            current_idx = state['waypoint_index']
            if current_idx + 1 < state['total_waypoints']:
                next_target = self.follower.waypoints[current_idx + 1]
                
                dx_next = next_target[0] - x
                dy_next = next_target[1] - y
                desired_yaw_next = math.atan2(dy_next, dx_next)
                
                angle_diff_next = desired_yaw_next - yaw
                while angle_diff_next > math.pi:
                    angle_diff_next -= 2 * math.pi
                while angle_diff_next < -math.pi:
                    angle_diff_next += 2 * math.pi
                angle_diff_next_deg = math.degrees(angle_diff_next)
                
                blend_ratio = 1.0 - (distance_to_waypoint / self.look_ahead_distance)
                blend_ratio = max(0.0, min(1.0, blend_ratio))
                
                angle_diff_current = state['angle_to_target']
                if angle_diff_current is not None:
                    angle_diff_current_deg = math.degrees(angle_diff_current)
                    blended_angle_diff = (1.0 - blend_ratio) * angle_diff_current_deg + \
                                         blend_ratio * angle_diff_next_deg
                    turn_rate = max(-self.max_turn_rate,
                                    min(self.max_turn_rate, 
                                        blended_angle_diff * self.proportional_gain))
                    if throttle > 0.0 and self.max_turn_rate > 0:
                        curvature_ratio = abs(turn_rate) / self.max_turn_rate
                        curvature_scale = 1.0 / (1.0 + self.curvature_speed_gain * curvature_ratio)
                        if curvature_scale <= self.min_speed_ratio:
                            throttle = 0.0
                        else:
                            throttle = min(throttle, max(self.min_speed_ratio, min(1.0, curvature_scale)))
                    throttle = max(0.0, min(1.0, throttle))
        
        self.last_throttle_command = throttle
        self.controller.send_command(throttle, -turn_rate)
        
        self.cmd_label.config(
            text=f"Waypoint {state['waypoint_index']+1}/{state['total_waypoints']} | "
                 f"Dist: {distance_to_waypoint:.2f}m | Throttle: {throttle:.2f}"
        )
        
        self.root.after(10, self._control_loop)
    
    def _stop(self):
        """Stop path following."""
        self.is_animating = False
        
        if self.controller.connected:
            self.controller.send_command(0.0, 0.0)
        
        if self.follower:
            self.follower.reset()
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.NORMAL)
        self.cmd_label.config(text="⏸ Stopped", fg='#ffaa00')
    
    def _emergency(self):
        """Emergency stop."""
        self.is_animating = False
        
        if self.controller.connected:
            self.controller.send_command(0.0, 0.0)
            print("[Controller] EMERGENCY STOP")
        
        if self.follower:
            self.follower.reset()
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.cmd_label.config(text="🛑 EMERGENCY", fg='#f44336')
    
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
            
            state = self.follower.get_state()
            if state['angle_to_target'] is not None:
                target_angle_deg = math.degrees(state['angle_to_target'])
                lines.append(f"Target Angle Error: {target_angle_deg:7.2f}°")
        else:
            lines.append("Predicted Location: N/A")
            lines.append("Predicted Rotation: N/A")
            lines.append("Target Angle Error: N/A")
        
        return "\n".join(lines)
    
    def _on_window_resize(self, event):
        """Handle window resize - adjust canvas to maintain aspect ratio."""
        # Only resize canvas widget events, not child widgets
        if event.widget != self.root:
            return
        
        # Get available space (window minus left panel ~280px, minus joystick if visible ~300px)
        window_width = event.width
        window_height = event.height
        
        # Calculate available canvas area
        left_panel_width = 280
        joystick_width = 300 if self.current_mode == self.MODE_RECORD else 0
        available_width = window_width - left_panel_width - joystick_width - 60  # padding
        available_height = window_height - 200  # title, labels, info panels
        
        # Maintain 16:9 aspect ratio
        aspect_ratio = 16 / 9
        
        # Calculate new canvas size while maintaining aspect ratio
        if available_width / available_height > aspect_ratio:
            # Limited by height
            new_height = max(400, available_height)
            new_width = int(new_height * aspect_ratio)
        else:
            # Limited by width
            new_width = max(800, available_width)
            new_height = int(new_width / aspect_ratio)
        
        # Only update if size changed significantly (more than 50px)
        if abs(new_width - self.canvas_width) > 50 or abs(new_height - self.canvas_height) > 50:
            self.canvas_width = new_width
            self.canvas_height = new_height
            
            # Update canvas size
            self.canvas.config(width=self.canvas_width, height=self.canvas_height)
            
            # Redraw grid with new dimensions
            self.canvas.delete('grid', 'origin')
            self.grid_helper.width = self.canvas_width
            self.grid_helper.height = self.canvas_height
            self.grid_helper.draw_grid()
            
            # Redraw robot if it exists
            if self.robot_visual:
                self._draw_robot()
    
    def shutdown(self):
        """Shutdown application."""
        print("\n[Controller] Shutting down...")
        
        self.is_animating = False
        if self.recording_service.is_recording:
            self.recording_service.stop_recording()
        
        if self.controller.connected:
            self.controller.send_command(0.0, 0.0)
        
        self.controller.shutdown()
        
        if self.tracking_active:
            self.tracker.stop()
        
        self.root.quit()
        print("[Controller] Complete")
    
    def run(self):
        """Run the application."""
        print(f"\n[Controller] Starting for {self.robot_name}")
        print("[Controller] Click 'Connect' to begin\n")
        self.root.mainloop()


def main():
    """Main entry point."""
    robot_name = 'umh_5'
    if len(sys.argv) > 1:
        robot_name = sys.argv[1]
    
    try:
        app = RobotControllerApp(robot_name=robot_name)
        app.run()
    except KeyboardInterrupt:
        print("\n[Controller] Interrupted")
    except Exception as e:
        print(f"[Controller] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
