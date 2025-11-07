#!/usr/bin/env python3
"""Hydra frontend controller application - Refactored with modular architecture."""

from __future__ import annotations

import math
import sys
import tkinter as tk
from pathlib import Path

from core.config_loader import load_config
from core.racing_config import RacingConfig
from frontend.udp_client import UDPClient
from services.recording_service import RecordingService
from services.path_service import PathService

# UI modules
from ui.tabbed_interface import TabbedInterface, CollapsibleSection
from ui.state import AppState
from ui.rendering import CanvasCoordinates, RobotRenderer
from ui.backend import BackendControllerProxy, RobotStateProxy, BackendMessageHandler, CommandSender
from ui.handlers import CanvasHandler, ButtonHandler, ModeHandler, RobotHandler, CanvasZoomPanHandler
from ui.widgets import RobotConfigPanel
from ui.tabs import DashboardTab, RobotsTab, PathPlanningTab, SettingsTab, MonitoringTab


class RobotControllerApp:
    """Frontend UI that communicates with the Hydra backend."""

    def __init__(self) -> None:
        # Initialize state
        self.state = AppState()
        
        # Load configuration
        self._load_config()

        # Setup UI
        self._setup_ui()
        
        # Setup services
        self._setup_services()
        
        # Setup handlers
        self._setup_handlers()
        
        # Setup tabs
        self._setup_tabs()
        
        # Wire up remaining UI components
        self._wire_ui_components()
        
        # Apply initial theming
        self.root.after(200, self._apply_active_robot_theme)

        # Bind window events
        self.root.bind("<Configure>", self._on_window_resize)
        self.root.after(500, self._auto_connect)

    def _load_config(self) -> None:
        """Load configuration and initialize robots."""
        self.config_loader = load_config()
        robot_config = self.config_loader.get_robot_config()
        hydra_host, hydra_port = self.config_loader.get_backend_endpoint()

        # Load canvas configuration
        canvas_config = self.config_loader.get_config().get("CANVAS_CONFIG", {})
        self.state.zoom = canvas_config.get("default_zoom", 1.0)
        self.state.min_zoom = canvas_config.get("min_zoom", 0.2)
        self.state.max_zoom = canvas_config.get("max_zoom", 5.0)
        self.state.zoom_step = canvas_config.get("zoom_step", 0.1)

        # Setup UDP client and backend proxy
        self.udp_client = UDPClient(hydra_host, hydra_port, on_message=self._on_backend_message)
        self.backend_controller = BackendControllerProxy(self.udp_client)
        self.command_sender = CommandSender(self.udp_client)
        self.message_handler = BackendMessageHandler(self.state)

        if not robot_config:
            raise RuntimeError("No robots defined in config.json")

        # Initialize robots
        self.state.robot_configs = robot_config
        for name, cfg in robot_config.items():
            robot_type = cfg.get("type", "real")
            self.state.robots[name] = RobotStateProxy(self, name, robot_type)
            self.state.racing_configs[name] = RacingConfig(name)
            self.state.robot_colors[name] = cfg.get("color", "#00aaff")
            self.state.set_robot_position(name, 0.0, 0.0, 0.0)

        self.state.active_robot = next(iter(self.state.robots.keys()))
        self.backend_controller.set_default_robot(self.state.active_robot)

    def _setup_ui(self) -> None:
        """Setup main UI window."""
        self.root = tk.Tk()
        self.root.title("🤖 Hydra Robot Swarm Controller")
        self.root.configure(bg="#0f0f0f")
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self.root.geometry("1800x1000")
        self.root.minsize(1200, 700)
        
        try:
            self.root.option_add("*Font", "{Segoe UI} 10")
        except:
            pass

        # Main container
        main_container = tk.Frame(self.root, bg="#0f0f0f")
        main_container.pack(fill=tk.BOTH, expand=True)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=1)

        # Create tabbed interface
        self.tabbed_ui = TabbedInterface(main_container, bg="#0f0f0f")
        
    def _setup_services(self) -> None:
        """Setup services."""
        # Coordinate converter
        self.coordinates = CanvasCoordinates(
            self.state.canvas_width,
            self.state.canvas_height,
            self.state.scale
        )
        
        # Path service (will be fully initialized after canvas is created)
        self.path_service = None
        
        # Recording service (will be fully initialized after canvas is created)
        self.recording_service = None
        
        # Robot renderer (will be initialized after canvas is created)
        self.robot_renderer = None

    def _setup_handlers(self) -> None:
        """Setup event handlers."""
        # Canvas handler (will be initialized after path service)
        self.canvas_handler = None
        
        # Button handler
        self.button_handler = ButtonHandler(
            self.state,
            None,  # path_service - will be set later
            self.command_sender,
            self.state.racing_configs,
            self._on_button_action
        )
        
        # Mode handler (will be initialized after recording service)
        self.mode_handler = None
        
        # Robot handler
        self.robot_handler = RobotHandler(
            self.state,
            self.config_loader,
            self.udp_client,
            self.command_sender,
            RacingConfig,
            RobotStateProxy,
            self._on_robot_action
        )

    def _setup_tabs(self) -> None:
        """Setup all tabs."""
        # Dashboard tab
        dashboard_frame = self.tabbed_ui.add_tab("Dashboard", "🏠")
        
        # Create temporary handlers for dashboard (will be updated after services are ready)
        temp_canvas_handler = type('obj', (object,), {
            'on_click': lambda e: None,
            'on_drag': lambda e: None,
            'on_release': lambda e: None
        })()
        temp_mode_handler = type('obj', (object,), {
            'switch_mode': lambda m: None
        })()
        
        self.dashboard_tab = DashboardTab(
            dashboard_frame,
            self.state,
            temp_canvas_handler,
            temp_mode_handler,
            self.button_handler
        )
        
        # Now that canvas exists, initialize services
        self._initialize_canvas_dependent_services()
        
        # Robots tab
        robots_frame = self.tabbed_ui.add_tab("Robots", "🤖")
        self.robots_tab = RobotsTab(robots_frame, self.state, self.robot_handler)
        
        # Path planning tab
        path_frame = self.tabbed_ui.add_tab("Path Planning", "📐")
        self.path_planning_tab = PathPlanningTab(path_frame, self.button_handler)
        
        # Settings tab
        settings_frame = self.tabbed_ui.add_tab("Settings", "⚙️")
        self.settings_tab = SettingsTab(settings_frame, self.state, self._on_setting_change)
        
        # Monitoring tab
        monitoring_frame = self.tabbed_ui.add_tab("Monitoring", "📊")
        self.monitoring_tab = MonitoringTab(monitoring_frame)

    def _initialize_canvas_dependent_services(self) -> None:
        """Initialize services that depend on canvas."""
        canvas = self.dashboard_tab.canvas
        
        # Initialize coordinate converter with zoom/pan
        self.coordinates.update_transform(self.state.zoom, self.state.pan_x, self.state.pan_y)
        
        # Update grid helper with coordinate converter
        self.dashboard_tab.grid_helper.coordinate_converter = self.coordinates
        
        # Path service
        self.path_service = PathService(
            canvas,
            self.coordinates.world_to_canvas,
            self.coordinates.canvas_to_world,
            color_provider=lambda r: self.state.robot_colors.get(r)
        )
        
        # Sync colors
        for rname, color in self.state.robot_colors.items():
            try:
                self.path_service.set_path_color(rname, color, redraw=False)
            except Exception:
                pass
        
        # Robot renderer
        self.robot_renderer = RobotRenderer(canvas, self.coordinates)
        
        # Recording service
        self.recording_service = RecordingService(
            self.backend_controller,
            self,
            self.state.robots[self.state.active_robot],
            canvas,
            self.coordinates.world_to_canvas,
        )
        self.recording_service.on_recording_start = self._on_recording_start
        self.recording_service.on_recording_stop = self._on_recording_stop
        self.recording_service.on_position_recorded = self._on_position_recorded
        self.recording_service.set_joystick_enabled(False)

        # Zoom/pan handler
        self.zoom_pan_handler = CanvasZoomPanHandler(
            canvas,
            self.state,
            self.coordinates,
            self._on_canvas_transform_change
        )
        
        # Now create real handlers
        self.canvas_handler = CanvasHandler(
            self.state,
            self.path_service,
            self._update_path_status
        )
        
        self.mode_handler = ModeHandler(
            self.state,
            self.recording_service,
            self._on_mode_change
        )
        
        # Update button handler with path service
        self.button_handler.path_service = self.path_service
        
        # Update dashboard tab with real handlers
        self.dashboard_tab.canvas_handler = self.canvas_handler
        self.dashboard_tab.mode_handler = self.mode_handler
        
        # Rebind canvas events with real handlers
        canvas.bind("<Button-1>", self.canvas_handler.on_click)
        canvas.bind("<B1-Motion>", self.canvas_handler.on_drag)
        canvas.bind("<ButtonRelease-1>", self.canvas_handler.on_release)

    def _wire_ui_components(self) -> None:
        """Wire up remaining UI components."""
        # Robot config panel
        self.robot_config_section = CollapsibleSection(
            self.dashboard_tab.robot_config_container,
            f"⚙️ {self.state.active_robot} Config",
            bg="#1e1e1e"
        )
        self.robot_config_section.pack(fill=tk.X)
        
        self.robot_config_panel = RobotConfigPanel(
            self.robot_config_section.content,
            self.state.racing_configs[self.state.active_robot],
            self._on_robot_config_change
        )
        self.robot_config_panel.pack(fill=tk.X)
        
        # Wire record button
        self.dashboard_tab.record_btn.config(command=self._toggle_recording)
        
        # Wire add robot button
        self.robots_tab.add_button.config(command=self._handle_add_robot)
        
        # Initialize robot dropdown
        self.dashboard_tab.robot_var.set(self.state.active_robot)
        self._update_robot_dropdown()

    # ------------------------------------------------------------------
    # Backend communication & scheduling
    # ------------------------------------------------------------------

    def _auto_connect(self) -> None:
        """Auto-connect to backend."""
        self._connect()

    def _connect(self) -> None:
        """Connect to backend."""
        self.dashboard_tab.status_label.config(text="🟡 Connecting to backend...", fg="#ffaa00")
        self.root.update()
        self.udp_client.start()
        self._sync_parameters_with_backend()
        self.state.tracking_active = True
        self.dashboard_tab.emergency_btn.config(state=tk.NORMAL)
        self._update_position()
        self._check_connection_status()

    def _check_connection_status(self) -> None:
        """Check and update connection status."""
        if not self.state.tracking_active:
            return
        
        status = self.udp_client.get_connection_status()
        connected = status.get("controlled_robots", []) if status else []
        num_real = len([r for r in self.state.robots.values() if r.robot_type == "real"])
        num_dummy = len([r for r in self.state.robots.values() if r.robot_type == "dummy"])

        if status and status.get("ros_connected", False):
            if len(connected) == num_real and num_real > 0:
                text = f"🟢 Connected: {len(connected)} real, {num_dummy} dummy"
                color = "#00ff88"
            else:
                text = f"🟡 Partial: {len(connected)}/{num_real} real, {num_dummy} dummy"
                color = "#ffaa00"
        else:
            text = "🔴 Backend offline"
            color = "#f44336"
        
        self.dashboard_tab.status_label.config(text=text, fg=color)
        self.monitoring_tab.update_status(text, color)
        
        self.root.after(500, self._check_connection_status)

    def _on_backend_message(self, message: dict) -> None:
        """Handle message from backend."""
        self.message_handler.handle_message(message)

    def _sync_parameters_with_backend(self) -> None:
        """Sync control parameters with backend."""
        params = {
            "use_prediction": self.state.use_prediction,
            "estimated_delay_ms": self.state.estimated_delay_ms,
            "waypoint_tolerance": 0.20,
            "turn_in_place_threshold": 65.0,
            "proportional_gain": 2.8,
            "max_turn_rate": 85.0,
            "slow_down_distance": 0.5,
            "min_speed_ratio": 0.20,
            "curvature_speed_gain": 0.65,
            "look_ahead_distance": 0.4,
            "path_simplification_tolerance": 0.06,
            "min_waypoint_separation": 0.15,
            "segment_pass_distance": 0.09,
            "segment_pass_lateral_factor": 1.7,
            "waypoint_approach_slowdown": 0.30,
            "corner_keep_angle_deg": 22.0,
            "intermediate_corner_slowdown_deg": 90.0,
            "throttle_ramp_rate": 0.9,
        }
        self.command_sender.sync_parameters(params)

    # ------------------------------------------------------------------
    # Event callbacks
    # ------------------------------------------------------------------

    def _on_button_action(self, action: str, *args):
        """Handle button actions."""
        if action == "start":
            robot_name = args[0]
            self.dashboard_tab.cmd_label.config(text=f"▶ {robot_name} following path...", fg="#00ff88")
            self._update_button_states()
            self.robots_tab.update_robot_list()
        elif action == "stop":
            robot_name = args[0]
            self.dashboard_tab.cmd_label.config(text=f"⏸ {robot_name} stopped", fg="#ffaa00")
            self._update_button_states()
            self.robots_tab.update_robot_list()
        elif action == "start_all":
            started = args[0]
            self.dashboard_tab.cmd_label.config(text=f"▶ {started} robots following paths...", fg="#00ff88")
            self._update_button_states()
            self.robots_tab.update_robot_list()
        elif action == "stop_all":
            self.dashboard_tab.cmd_label.config(text="⏸ All stopped", fg="#ffaa00")
            self._update_button_states()
            self.robots_tab.update_robot_list()
        elif action == "emergency":
            self.dashboard_tab.cmd_label.config(text="🛑 EMERGENCY", fg="#f44336")
        elif action == "clear":
            mode = self.state.current_mode
            if mode == self.state.MODE_CLICK:
                self.dashboard_tab.cmd_label.config(text=f"📍 {self.state.active_robot}: Click to add waypoints", fg="#fff")
            elif mode == self.state.MODE_DRAW:
                self.dashboard_tab.cmd_label.config(text=f"✏️ {self.state.active_robot}: Drag to draw path", fg="#00aaff")
            else:
                self.dashboard_tab.cmd_label.config(text=f"🎮 {self.state.active_robot}: Use joystick", fg="#ff6600")
            self._update_button_states()
            self._update_path_status()
        elif action == "save":
            self._update_path_status()
        elif action == "load":
            info = args[0]
            self.dashboard_tab.cmd_label.config(
                text=f"✓ {self.state.active_robot}: {info['num_waypoints']} waypoints loaded",
                fg="#00ff88",
            )
            self._update_button_states()
            self._update_path_status()

    def _on_mode_change(self, mode: str):
        """Handle mode change."""
        self.dashboard_tab.update_mode_buttons()
        
        if mode == self.state.MODE_CLICK:
            self.dashboard_tab.cmd_label.config(text=f"📍 {self.state.active_robot}: Click to add waypoints", fg="#fff")
            self.dashboard_tab.canvas.config(cursor="")
            self.dashboard_tab.joystick_container.grid_remove()
            self.recording_service.set_joystick_enabled(False)
        elif mode == self.state.MODE_DRAW:
            self.dashboard_tab.cmd_label.config(text=f"✏️ {self.state.active_robot}: Drag to draw path", fg="#00aaff")
            self.dashboard_tab.canvas.config(cursor="pencil")
            self.dashboard_tab.joystick_container.grid_remove()
            self.recording_service.set_joystick_enabled(False)
        else:
            self.dashboard_tab.cmd_label.config(text=f"🎮 {self.state.active_robot}: Use joystick", fg="#ff6600")
            self.dashboard_tab.canvas.config(cursor="")
            self.dashboard_tab.joystick_container.grid(row=1, column=1, sticky="ns", padx=(10, 0))
            self.dashboard_tab.joystick_container.grid_propagate(False)
            self.recording_service.set_joystick_enabled(True)

    def _on_robot_action(self, action: str, *args):
        """Handle robot management actions."""
        if action == "select":
            robot_name = args[0]
            self._on_robot_change(robot_name)
            self.robots_tab.update_robot_list()
        elif action == "add":
            robot_name = args[0]
            self.path_service.set_path_color(robot_name, self.state.robot_colors[robot_name], redraw=False)
            self._update_robot_dropdown()
            self._select_robot(robot_name)
            self.robots_tab.update_robot_list()
    
    def _update_robot_dropdown(self):
        """Update the robot dropdown menu."""
        menu = self.dashboard_tab.robot_dropdown["menu"]
        menu.delete(0, "end")
        for name in self.state.robots.keys():
            menu.add_command(label=name, command=lambda value=name: self._select_robot(value))

    def _on_robot_config_change(self, param: str, value):
        """Handle robot config change."""
        self.command_sender.send_racing_config(
            self.state.active_robot,
            self.state.racing_configs[self.state.active_robot]
        )

    def _on_setting_change(self, setting: str):
        """Handle settings change."""
        self._sync_parameters_with_backend()
    
    def _on_canvas_transform_change(self):
        """Handle canvas zoom/pan transform change."""
        # Redraw grid
        self.dashboard_tab.grid_helper.draw_grid()
        
        # Redraw robots
        self._draw_robots()
        
        # Redraw all paths
        for robot_name in self.state.robots.keys():
            if robot_name in self.path_service.robot_paths:
                self.path_service._redraw_path(robot_name)

    def _select_robot(self, robot_name: str) -> None:
        """Select a robot."""
        if robot_name not in self.state.robots:
            return
        self.robot_handler.select_robot(robot_name)

    def _on_robot_change(self, robot_name: str) -> None:
        """Handle robot selection change."""
        self.state.active_robot = robot_name
        self.backend_controller.set_default_robot(robot_name)
        self.recording_service.robot = self.state.robots[robot_name]
        
        # Update config panel
        self.robot_config_panel.update_config(self.state.racing_configs[robot_name])
        self.robot_config_section.title_label.config(text=f"⚙️ {robot_name} Config")
        
        # Update robot dropdown
        self.dashboard_tab.robot_var.set(robot_name)
        self._update_robot_dropdown()
        
        self._apply_active_robot_theme()
        self._update_button_states()
        self._update_path_status()

    def _handle_add_robot(self) -> None:
        """Handle add robot request."""
        name = self.robots_tab.add_robot_name_var.get().strip()
        umh_id = self.robots_tab.add_robot_umh_var.get().strip()
        robot_type = self.robots_tab.add_robot_type_var.get().strip().lower() or "real"
        self.robot_handler.add_robot(name, umh_id, robot_type, self)

    # ------------------------------------------------------------------
    # Recording callbacks
    # ------------------------------------------------------------------

    def _toggle_recording(self) -> None:
        """Toggle recording."""
        if not self.state.tracking_active or not self.backend_controller.connected:
            from tkinter import messagebox
            messagebox.showwarning("Recording", "Please connect to the backend first.")
            return
        
        if self.recording_service.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        """Start recording."""
        self.path_service.clear_path(self.state.active_robot)
        if self.recording_service.start_recording():
            self.dashboard_tab.record_btn.config(text="⏹ STOP RECORDING", style="success")
            self.dashboard_tab.cmd_label.config(text=f"🎮 Recording {self.state.active_robot}...", fg="#f44336")
            self.path_planning_tab.save_btn.config(state=tk.DISABLED)
            self.path_planning_tab.load_btn.config(state=tk.DISABLED)

    def _stop_recording(self) -> None:
        """Stop recording."""
        recorded = self.recording_service.stop_recording()
        self.dashboard_tab.record_btn.config(text="⏺ START RECORDING", style="danger")
        self.path_planning_tab.save_btn.config(state=tk.NORMAL)
        self.path_planning_tab.load_btn.config(state=tk.NORMAL)
        
        if recorded:
            self.path_service.set_recorded_path(self.state.active_robot, recorded)
            self.dashboard_tab.cmd_label.config(
                text=f"🎮 {self.state.active_robot}: {len(recorded)} points recorded",
                fg="#00ff88",
            )
            self._update_button_states()
        else:
            self.dashboard_tab.cmd_label.config(text="🎮 No motion recorded", fg="#FFA500")

    def _on_recording_start(self):
        """Recording started callback."""
        pass

    def _on_recording_stop(self):
        """Recording stopped callback."""
        pass

    def _on_position_recorded(self, count: int) -> None:
        """Position recorded callback."""
        self.dashboard_tab.cmd_label.config(text=f"🎮 Recording {self.state.active_robot}... {count} points", fg="#f44336")

    # ------------------------------------------------------------------
    # UI updates
    # ------------------------------------------------------------------

    def _update_path_status(self) -> None:
        """Update path status display."""
        info = self.path_service.get_path_info(self.state.active_robot)
        mode_name = "📍 Click" if self.state.current_mode == self.state.MODE_CLICK else "✏️ Draw"
        total_paths = sum(1 for r in self.state.robots if self.path_service.has_path(r))
        
        status_text = f"{mode_name} | {self.state.active_robot}: {info['num_waypoints']} pts"
        if total_paths > 1:
            status_text += f" | {total_paths} robots have paths"
        self.dashboard_tab.cmd_label.config(text=status_text)
        
        # Update path info in Path Planning tab
        path_info = f"Active Robot: {self.state.active_robot}\n"
        path_info += f"Waypoints: {info['num_waypoints']}\n"
        path_info += f"Is Recorded: {'Yes' if info['is_recorded'] else 'No'}\n"
        path_info += f"Total Robots with Paths: {total_paths}"
        self.path_planning_tab.update_path_info(path_info)
        
        self._update_button_states()

    def _update_button_states(self) -> None:
        """Update button states based on current state."""
        active_followers = self.state.get_follower_states()
        has_path = self.path_service.has_path(self.state.active_robot)
        is_following = self.state.active_robot in active_followers
        
        self.dashboard_tab.start_btn.config(state=tk.NORMAL if has_path else tk.NORMAL)
        self.dashboard_tab.stop_btn.config(state=tk.NORMAL if is_following else tk.DISABLED)
        
        any_has_path = any(self.path_service.has_path(r) for r in self.state.robots.keys())
        any_following = bool(active_followers)
        
        self.dashboard_tab.start_all_btn.config(state=tk.NORMAL if any_has_path else tk.DISABLED)
        self.dashboard_tab.stop_all_btn.config(state=tk.NORMAL if any_following else tk.DISABLED)

    def _update_position(self) -> None:
        """Update robot positions and rendering."""
        if not self.state.tracking_active:
            return
        
        self._draw_robots()
        x, y, yaw = self.state.get_robot_position(self.state.active_robot)
        yaw_deg = math.degrees(yaw)
        robot_type = self.state.robots[self.state.active_robot].robot_type
        prefix = "🤖" if robot_type == "real" else "🎮"
        
        # Update positions label in Monitoring tab
        positions_text = f"{prefix} {self.state.active_robot}: ({x:6.3f}, {y:6.3f})m | {yaw_deg:6.1f}°\n\n"
        for name, proxy in self.state.robots.items():
            if name != self.state.active_robot:
                rx, ry, ryaw = self.state.get_robot_position(name)
                rprefix = "🤖" if proxy.robot_type == "real" else "🎮"
                positions_text += f"{rprefix} {name}: ({rx:6.3f}, {ry:6.3f})m | {math.degrees(ryaw):6.1f}°\n"
        self.monitoring_tab.update_positions(positions_text)
        
        # Update debug info
        self.monitoring_tab.update_debug(self._get_debug_info())
        
        # Process joystick if active
        if self.recording_service.joystick_control_active:
            joy_x, joy_y = self.dashboard_tab.joystick.get_values()
            self.recording_service.process_joystick_input(joy_x, joy_y)
        
        self.root.after(50, self._update_position)

    def _draw_robots(self) -> None:
        """Draw all robots on canvas."""
        # Clear old visuals
        for visual in list(self.state.robot_visuals.values()):
            self.dashboard_tab.canvas.delete(visual)
        self.state.robot_visuals.clear()
        
        # Get current state
        positions = self.state.get_robot_positions()
        followers = set(self.state.get_follower_states().keys())
        
        # Draw robots
        self.state.robot_visuals = self.robot_renderer.draw_robots(
            self.state.robots,
            positions,
            followers,
            self.state.robot_colors,
            self.state.active_robot,
            self.path_service.has_path
            )

    def _apply_active_robot_theme(self) -> None:
        """Apply active robot color theme to UI."""
        if not self.state.active_robot or not self.state.robot_colors:
            return
        
        color = self.state.robot_colors.get(self.state.active_robot, "#00aaff")
        
        # Determine text color
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
        except Exception:
            r, g, b = 0, 170, 255
        
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        fg = "#000000" if luminance > 140 else "#ffffff"
        
        # Apply to buttons
        for btn in [self.dashboard_tab.start_btn, self.dashboard_tab.stop_btn, self.dashboard_tab.emergency_btn]:
            try:
                if hasattr(btn, 'set_custom_color'):
                    btn.set_custom_color(color, fg)
            except Exception:
                pass
        
        # Update command label
        try:
            self.dashboard_tab.cmd_label.config(fg=color)
        except Exception:
            pass

    def _get_debug_info(self) -> str:
        """Get debug information text."""
        x, y, yaw = self.state.get_robot_position(self.state.active_robot)
        yaw_deg = math.degrees(yaw)
        follower = self.state.get_follower_states().get(self.state.active_robot)
        
        lines = [
            f"Current Location:  ({x:6.3f}m, {y:6.3f}m)",
            f"Current Rotation:  {yaw_deg:7.2f}°",
        ]
        
        if follower:
            lines.append(f"Waypoint {follower.get('waypoint_index', 0)+1}/{follower.get('total_waypoints', 0)}")
            dist = follower.get("distance_to_target")
            if dist is not None:
                lines.append(f"Distance to Target: {dist:.3f}m")
            throttle = follower.get("throttle")
            if throttle is not None:
                lines.append(f"Throttle: {throttle:.2f}")
        else:
            lines.append("Follower State: N/A")
        
        return "\n".join(lines)

    def _on_window_resize(self, event) -> None:
        """Handle window resize."""
        if event.widget != self.root:
            return
        
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        
        status_bar_height = 60
        tab_bar_height = 55
        padding = 40
        
        left_panel_width = 360
        joystick_width = 320 if self.state.current_mode == self.state.MODE_RECORD else 0
        available_width = window_width - left_panel_width - joystick_width - padding
        available_height = window_height - status_bar_height - tab_bar_height - padding
        
        if available_width < 400 or available_height < 300:
            return
        
        aspect_ratio = 16 / 9
        target_aspect = available_width / available_height
        
        if target_aspect > aspect_ratio:
            new_height = max(300, available_height)
            new_width = int(new_height * aspect_ratio)
        else:
            new_width = max(400, available_width)
            new_height = int(new_width / aspect_ratio)
        
        if abs(new_width - self.state.canvas_width) > 30 or abs(new_height - self.state.canvas_height) > 30:
            self.state.canvas_width = new_width
            self.state.canvas_height = new_height
            self.dashboard_tab.canvas.config(width=self.state.canvas_width, height=self.state.canvas_height)
            self.dashboard_tab.canvas.delete("grid", "origin")
            self.coordinates.update_dimensions(self.state.canvas_width, self.state.canvas_height)
            self.dashboard_tab.grid_helper.width = self.state.canvas_width
            self.dashboard_tab.grid_helper.height = self.state.canvas_height
            self.dashboard_tab.grid_helper.draw_grid()
            
            if self.state.robot_visuals:
                self._draw_robots()
            
            for robot_name in self.state.robots.keys():
                if robot_name in self.path_service.robot_paths:
                    self.path_service._redraw_path(robot_name)

    def shutdown(self) -> None:
        """Shutdown application."""
        print("\n[Controller] Shutting down...")
        if self.recording_service.is_recording:
            self.recording_service.stop_recording()
        self.command_sender.stop_all()
        self.udp_client.close()
        self.root.quit()
        print("[Controller] Complete")

    def run(self) -> None:
        """Run the application."""
        print(f"\n[Controller] Starting with {len(self.state.robots)} robots")
        print("[Controller] Auto-connecting...\n")
        self.root.mainloop()


def main() -> None:
    try:
        app = RobotControllerApp()
        app.run()
    except KeyboardInterrupt:
        print("\n[Controller] Interrupted")
    except Exception as exc:
        print(f"[Controller] Error: {exc}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
