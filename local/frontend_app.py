#!/usr/bin/env python3
"""Hydra frontend controller application - Redesigned with Tabbed Interface."""

from __future__ import annotations

import math
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

import tkinter as tk
from tkinter import messagebox, ttk

from core.config_loader import load_config
from frontend.udp_client import UDPClient
from ui.virtual_joystick import VirtualJoystick
from ui.components import (
    ModernButton,
    StatusLabel,
    ModernFrame,
    ModernScale,
    ModernCheckbutton,
    CanvasGrid,
)
from ui.tabbed_interface import TabbedInterface, CollapsibleSection
from services.recording_service import RecordingService
from services.path_service import PathService
from core.racing_config import RacingConfig


class BackendControllerProxy:
    """Proxy that forwards control commands to the backend via UDP."""

    def __init__(self, udp_client: UDPClient):
        self._udp_client = udp_client
        self._default_robot: Optional[str] = None

    @property
    def connected(self) -> bool:
        status = self._udp_client.get_connection_status()
        if not status:
            return False
        return bool(status.get("ros_connected", False))

    def set_default_robot(self, robot_name: str) -> None:
        self._default_robot = robot_name

    def send_command(self, throttle: float, angle: float, robot_name: Optional[str] = None) -> bool:
        target = robot_name or self._default_robot
        if not target:
            return False
        payload = {
            "type": "manual_control",
            "data": {
                "robot": target,
                "throttle": float(throttle),
                "turn_rate": float(angle),
            },
        }
        self._udp_client.send(payload)
        return True


class RobotStateProxy:
    """Minimal robot facade for UI services relying on position queries."""

    def __init__(self, app: "RobotControllerApp", name: str, robot_type: str):
        self._app = app
        self.username = name
        self.robot_type = robot_type

    def get_position(self):
        return self._app.get_robot_position(self.username)

    def set_location(self, x: float, y: float, yaw: float = 0.0) -> None:
        self._app.set_robot_position(self.username, x, y, yaw)


class RobotControllerApp:
    """Frontend UI that communicates with the Hydra backend."""

    MODE_CLICK = "click"
    MODE_DRAW = "draw"
    MODE_RECORD = "record"

    def __init__(self) -> None:
        self.current_mode = self.MODE_CLICK
        self.canvas_width = 1200
        self.canvas_height = 675
        self.scale = 50

        self.tracking_active = False
        self.is_drawing = False
        self.last_draw_point = None
        self.draw_sample_distance = 15
        self.robot_visuals: Dict[str, int] = {}

        self._state_lock = threading.Lock()

        self.config_loader = load_config()
        self._load_config()

        self._setup_ui()
        self._setup_services()
        # Apply initial theming based on active robot (after UI is fully rendered)
        # Use a longer delay to ensure all widgets are created and visible
        self.root.after(200, self._apply_active_robot_theme)

        self.root.bind("<Configure>", self._on_window_resize)
        self.root.after(500, self._auto_connect)

    # ------------------------------------------------------------------
    # Configuration & state helpers
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        robot_config = self.config_loader.get_robot_config()
        hydra_host, hydra_port = self.config_loader.get_backend_endpoint()

        self.udp_client = UDPClient(hydra_host, hydra_port, on_message=self._on_backend_message)
        self.backend_controller = BackendControllerProxy(self.udp_client)

        if not robot_config:
            raise RuntimeError("No robots defined in config.json")

        self.robots: Dict[str, RobotStateProxy] = {}
        self.robot_configs: Dict[str, Dict] = robot_config
        self.racing_configs: Dict[str, RacingConfig] = {}

        self.robot_colors: Dict[str, str] = {}
        for name, cfg in robot_config.items():
            robot_type = cfg.get("type", "real")
            self.robots[name] = RobotStateProxy(self, name, robot_type)
            self.racing_configs[name] = RacingConfig(name)
            color = cfg.get("color", "#00aaff")
            self.robot_colors[name] = color

        self.active_robot = next(iter(self.robots.keys()))
        self.backend_controller.set_default_robot(self.active_robot)

        self.robot_states: Dict[str, Dict[str, float]] = {}
        self.robot_positions: Dict[str, tuple[float, float, float]] = {
            name: (0.0, 0.0, 0.0) for name in self.robots.keys()
        }
        self.follower_states: Dict[str, Dict[str, float]] = {}
        self.connection_status: Dict[str, object] = {}

    def get_robot_position(self, name: str):
        with self._state_lock:
            return self.robot_positions.get(name, (0.0, 0.0, 0.0))

    def set_robot_position(self, name: str, x: float, y: float, yaw: float) -> None:
        with self._state_lock:
            self.robot_positions[name] = (x, y, yaw)

    # ------------------------------------------------------------------
    # UI setup - Redesigned with Tabs
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.root = tk.Tk()
        self.root.title("🤖 Hydra Robot Swarm Controller")
        self.root.configure(bg="#0f0f0f")
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        # Start with a larger default window for better visibility
        self.root.geometry("1800x1000")
        self.root.minsize(1200, 700)  # Set minimum window size
        # Try to set a better default font
        try:
            # Use braces to quote family names with spaces for Tk
            self.root.option_add("*Font", "{Segoe UI} 10")
        except:
            pass

        # Main container with proper weight configuration for resizing
        main_container = tk.Frame(self.root, bg="#0f0f0f")
        main_container.pack(fill=tk.BOTH, expand=True)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=1)

        # Create tabbed interface
        self.tabbed_ui = TabbedInterface(main_container, bg="#0f0f0f")
        
        # Setup all tabs
        self._setup_dashboard_tab()
        self._setup_robots_tab()
        self._setup_path_planning_tab()
        self._setup_settings_tab()
        self._setup_monitoring_tab()

    def _setup_dashboard_tab(self) -> None:
        """Dashboard tab - Main control view with improved organization."""
        dashboard_frame = self.tabbed_ui.add_tab("Dashboard", "🏠")
        
        # Configure grid weights for proper resizing
        dashboard_frame.grid_rowconfigure(1, weight=1)
        dashboard_frame.grid_columnconfigure(0, weight=1)
        
        # Top status bar with enhanced styling
        status_bar = tk.Frame(dashboard_frame, bg="#1e1e1e", height=60)
        status_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        status_bar.grid_propagate(False)
        status_bar.grid_columnconfigure(1, weight=1)
        
        # Status indicator on left
        status_left = tk.Frame(status_bar, bg="#1e1e1e")
        status_left.grid(row=0, column=0, sticky="w", padx=20, pady=10)
        self.status_label = StatusLabel(status_left, text="⚪ Not Connected", fg="#9e9e9e")
        self.status_label.pack(side=tk.LEFT)
        
        # Quick robot selector on right
        robot_selector_frame = tk.Frame(status_bar, bg="#1e1e1e")
        robot_selector_frame.grid(row=0, column=1, sticky="e", padx=20, pady=10)
        
        tk.Label(robot_selector_frame, text="Active Robot:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
        self.robot_var = tk.StringVar(value=self.active_robot)
        self.robot_dropdown = tk.OptionMenu(
            robot_selector_frame,
            self.robot_var,
            *self.robots.keys(),
            command=lambda value: self._select_robot(value),
        )
        self.robot_dropdown.config(
            bg="#2d2d2d",
            fg="#ffffff",
            font=("Segoe UI", 10),
            highlightthickness=0,
            activebackground="#00d4aa",
            activeforeground="#000000",
        )
        self.robot_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Main content area with proper grid configuration
        content_area = tk.Frame(dashboard_frame, bg="#0f0f0f")
        content_area.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        content_area.grid_rowconfigure(0, weight=1)
        content_area.grid_columnconfigure(1, weight=1)  # Canvas column gets weight
        
        # Left sidebar with controls - fixed width but scrollable
        sidebar = tk.Frame(content_area, bg="#1e1e1e", width=360)
        sidebar.grid(row=0, column=0, sticky="ns", padx=0, pady=0)
        sidebar.grid_propagate(False)
        
        # Scrollable sidebar content
        sidebar_canvas = tk.Canvas(sidebar, bg="#1e1e1e", highlightthickness=0)
        sidebar_scrollbar = tk.Scrollbar(sidebar, orient=tk.VERTICAL, command=sidebar_canvas.yview)
        sidebar_content = tk.Frame(sidebar_canvas, bg="#1e1e1e")
        
        sidebar_content.bind("<Configure>", lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all")))
        sidebar_canvas.create_window((0, 0), window=sidebar_content, anchor="nw")
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        
        sidebar_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sidebar_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Quick Controls Section
        quick_controls = CollapsibleSection(sidebar_content, "⚡ Quick Controls", bg="#1e1e1e")
        quick_controls.pack(fill=tk.X, padx=10, pady=8)
        
        self.start_btn = ModernButton(
            quick_controls.content,
            text="▶ START PATH",
            style="success",
            command=self._start,
            state=tk.DISABLED,
        )
        self.start_btn.config(pady=12, font=("Segoe UI", 11, "bold"))
        self.start_btn.pack(fill=tk.X, padx=8, pady=4)
        
        self.stop_btn = ModernButton(
            quick_controls.content,
            text="⏸ STOP",
            style="warning",
            command=self._stop,
            state=tk.DISABLED,
        )
        self.stop_btn.config(pady=12, font=("Segoe UI", 11, "bold"))
        self.stop_btn.pack(fill=tk.X, padx=8, pady=4)
        
        self.emergency_btn = ModernButton(
            quick_controls.content,
            text="🛑 EMERGENCY STOP",
            style="danger",
            command=self._emergency,
            state=tk.DISABLED,
        )
        self.emergency_btn.config(pady=12, font=("Segoe UI", 11, "bold"))
        self.emergency_btn.pack(fill=tk.X, padx=8, pady=4)
        
        btn_frame = tk.Frame(quick_controls.content, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X, padx=8, pady=4)
        self.start_all_btn = ModernButton(
            btn_frame,
            text="▶ ALL",
            style="success",
            command=self._start_all,
        )
        self.start_all_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.stop_all_btn = ModernButton(
            btn_frame,
            text="⏸ ALL",
            style="warning",
            command=self._stop_all,
        )
        self.stop_all_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Mode Selection Section
        mode_section = CollapsibleSection(sidebar_content, "🎯 Path Creation Mode", bg="#1e1e1e")
        mode_section.pack(fill=tk.X, padx=10, pady=8)
        
        self.mode_buttons: Dict[str, tk.Button] = {}
        modes = [
            (self.MODE_CLICK, "📍 Click Mode"),
            (self.MODE_DRAW, "✏️ Draw Mode"),
            (self.MODE_RECORD, "🎮 Record Mode"),
        ]
        for mode_id, label in modes:
            btn = ModernButton(
                mode_section.content,
                text=label,
                style="secondary",
                command=lambda value=mode_id: self._switch_mode(value),
            )
            btn.pack(fill=tk.X, padx=8, pady=4)
            self.mode_buttons[mode_id] = btn
        self._update_mode_buttons()
        
        # Active Robot Config Section
        self.robot_config_section = CollapsibleSection(sidebar_content, f"⚙️ {self.active_robot} Config", bg="#1e1e1e")
        self.robot_config_section.pack(fill=tk.X, padx=10, pady=8)
        
        # Offset
        offset_frame = tk.Frame(self.robot_config_section.content, bg="#1e1e1e")
        offset_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(offset_frame, text="Lateral Offset:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10)).pack(anchor=tk.W)
        offset_control = tk.Frame(offset_frame, bg="#1e1e1e")
        offset_control.pack(fill=tk.X, pady=3)
        self.offset_var = tk.DoubleVar(value=0.0)
        offset_scale = ModernScale(
            offset_control,
            from_=-0.5,
            to=0.5,
            orient=tk.HORIZONTAL,
            variable=self.offset_var,
            command=self._on_offset_change,
            resolution=0.05,
        )
        offset_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.offset_label = tk.Label(
            offset_control,
            text="0.0m",
            bg="#1e1e1e",
            fg="#00d4aa",
            font=("Segoe UI", 10, "bold"),
            width=6,
        )
        self.offset_label.pack(side=tk.LEFT, padx=8)
        
        # Speed
        speed_frame = tk.Frame(self.robot_config_section.content, bg="#1e1e1e")
        speed_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(speed_frame, text="Speed Multiplier:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10)).pack(anchor=tk.W)
        speed_control = tk.Frame(speed_frame, bg="#1e1e1e")
        speed_control.pack(fill=tk.X, pady=3)
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_scale = ModernScale(
            speed_control,
            from_=0.3,
            to=1.5,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            command=self._on_speed_change,
            resolution=0.1,
        )
        speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.speed_label = tk.Label(
            speed_control,
            text="1.0x",
            bg="#1e1e1e",
            fg="#00d4aa",
            font=("Segoe UI", 10, "bold"),
            width=6,
        )
        self.speed_label.pack(side=tk.LEFT, padx=8)
        
        # Loop checkbox
        self.loop_var = tk.BooleanVar(value=False)
        loop_check = ModernCheckbutton(
            self.robot_config_section.content,
            text="Loop Circuit",
            variable=self.loop_var,
            command=self._on_loop_change,
        )
        loop_check.pack(anchor=tk.W, padx=8, pady=4)
        
        # Canvas area - uses grid for better resizing
        canvas_container = tk.Frame(content_area, bg="#0f0f0f")
        canvas_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        canvas_container.grid_rowconfigure(1, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)  # Canvas column
        canvas_container.grid_columnconfigure(1, weight=0)  # Joystick column (fixed width)
        
        # Canvas header
        self.cmd_label = tk.Label(
            canvas_container,
            text="📍 Click mode: Click to add waypoints",
            font=("Segoe UI", 11, "bold"),
            bg="#1e1e1e",
            fg="#ffffff",
            pady=12,
        )
        self.cmd_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        
        # Canvas wrapper with proper grid configuration
        canvas_wrapper = tk.Frame(canvas_container, bg="#1e1e1e", bd=0, relief=tk.FLAT, highlightbackground="#333333", highlightthickness=1)
        canvas_wrapper.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        canvas_wrapper.grid_rowconfigure(0, weight=1)
        canvas_wrapper.grid_columnconfigure(0, weight=1)
        
        # Canvas with proper resizing
        self.canvas = tk.Canvas(
            canvas_wrapper,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#0a0a0a",
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        
        self.grid_helper = CanvasGrid(self.canvas, self.scale, self.canvas_width, self.canvas_height)
        self.grid_helper.draw_grid()
        
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        
        # Joystick container (hidden by default) - uses grid
        self.joystick_container = tk.Frame(canvas_container, bg="#0f0f0f", width=320)
        joystick_frame = tk.LabelFrame(
            self.joystick_container,
            text="🕹️ JOYSTICK",
            font=("Segoe UI", 11, "bold"),
            bg="#1e1e1e",
            fg="#00d4aa",
            bd=0,
            relief=tk.FLAT,
            highlightbackground="#333333",
            highlightthickness=1,
        )
        joystick_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.joystick = VirtualJoystick(joystick_frame, size=250)
        self.joystick.pack(padx=15, pady=15)
        self.record_btn = ModernButton(
            joystick_frame,
            text="⏺ START RECORDING",
            style="danger",
            command=self._toggle_recording,
        )
        self.record_btn.config(pady=12, font=("Segoe UI", 11, "bold"))
        self.record_btn.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        # Mouse wheel scrolling for sidebar
        def _on_mousewheel(event):
            sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        sidebar_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        sidebar_canvas.bind_all("<Button-4>", lambda e: sidebar_canvas.yview_scroll(-1, "units"))
        sidebar_canvas.bind_all("<Button-5>", lambda e: sidebar_canvas.yview_scroll(1, "units"))

    def _setup_robots_tab(self) -> None:
        """Robots tab - Robot management with improved organization."""
        robots_frame = self.tabbed_ui.add_tab("Robots", "🤖")
        
        # Use grid layout for better organization
        robots_frame.grid_rowconfigure(0, weight=1)
        robots_frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable content with improved layout
        robots_canvas = tk.Canvas(robots_frame, bg="#0f0f0f", highlightthickness=0)
        robots_scrollbar = tk.Scrollbar(robots_frame, orient=tk.VERTICAL, command=robots_canvas.yview)
        robots_content = tk.Frame(robots_canvas, bg="#0f0f0f")
        
        robots_content.bind("<Configure>", lambda e: robots_canvas.configure(scrollregion=robots_canvas.bbox("all")))
        robots_canvas.create_window((0, 0), window=robots_content, anchor="nw")
        robots_canvas.configure(yscrollcommand=robots_scrollbar.set)
        
        robots_canvas.grid(row=0, column=0, sticky="nsew")
        robots_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Configure content frame to expand
        robots_content.grid_columnconfigure(0, weight=1)
        
        # Robot List Section
        robot_list_section = CollapsibleSection(robots_content, "📋 Robot List", bg="#1e1e1e", expanded=True)
        robot_list_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Robot list display with improved styling
        self.robot_list_frame = tk.Frame(robot_list_section.content, bg="#1e1e1e")
        self.robot_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._update_robot_list_display()
        
        # Add Robot Section
        add_robot_section = CollapsibleSection(robots_content, "➕ Add New Robot", bg="#1e1e1e", expanded=True)
        add_robot_section.pack(fill=tk.X, padx=15, pady=15)
        
        add_form = tk.Frame(add_robot_section.content, bg="#1e1e1e")
        add_form.pack(fill=tk.X, padx=15, pady=15)
        
        # Name
        tk.Label(add_form, text="Robot Name:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, padx=10, pady=8)
        self.add_robot_name_var = tk.StringVar()
        name_entry = tk.Entry(add_form, textvariable=self.add_robot_name_var, bg="#2d2d2d", fg="#fff", font=("Segoe UI", 10), insertbackground="#fff", relief=tk.FLAT, bd=2)
        name_entry.grid(row=0, column=1, sticky=tk.EW, padx=10, pady=8)
        
        # UMH ID
        tk.Label(add_form, text="UMH ID:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky=tk.W, padx=10, pady=8)
        self.add_robot_umh_var = tk.StringVar()
        umh_entry = tk.Entry(add_form, textvariable=self.add_robot_umh_var, bg="#2d2d2d", fg="#fff", font=("Segoe UI", 10), insertbackground="#fff", relief=tk.FLAT, bd=2)
        umh_entry.grid(row=1, column=1, sticky=tk.EW, padx=10, pady=8)
        
        # Type
        tk.Label(add_form, text="Type:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky=tk.W, padx=10, pady=8)
        self.add_robot_type_var = tk.StringVar(value="real")
        type_menu = tk.OptionMenu(add_form, self.add_robot_type_var, "real", "dummy")
        type_menu.config(bg="#2d2d2d", fg="#fff", highlightthickness=0, font=("Segoe UI", 10), activebackground="#00d4aa", relief=tk.FLAT, bd=2)
        type_menu.grid(row=2, column=1, sticky=tk.EW, padx=10, pady=8)
        
        # Add button
        add_button = ModernButton(add_form, text="➕ Add Robot", style="primary", command=self._handle_add_robot)
        add_button.grid(row=3, column=0, columnspan=2, pady=15, padx=10, sticky="ew")
        
        add_form.columnconfigure(1, weight=1)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            robots_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        robots_canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _setup_path_planning_tab(self) -> None:
        """Path Planning tab - Path creation and management with improved layout."""
        path_frame = self.tabbed_ui.add_tab("Path Planning", "📐")
        
        # Use grid layout for better organization
        path_frame.grid_rowconfigure(0, weight=1)
        path_frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable content
        path_canvas = tk.Canvas(path_frame, bg="#0f0f0f", highlightthickness=0)
        path_scrollbar = tk.Scrollbar(path_frame, orient=tk.VERTICAL, command=path_canvas.yview)
        path_content = tk.Frame(path_canvas, bg="#0f0f0f")
        
        path_content.bind("<Configure>", lambda e: path_canvas.configure(scrollregion=path_canvas.bbox("all")))
        path_canvas.create_window((0, 0), window=path_content, anchor="nw")
        path_canvas.configure(yscrollcommand=path_scrollbar.set)
        
        path_canvas.grid(row=0, column=0, sticky="nsew")
        path_scrollbar.grid(row=0, column=1, sticky="ns")
        path_frame.grid_columnconfigure(0, weight=1)
        
        # Path Management Section
        path_mgmt_section = CollapsibleSection(path_content, "📁 Path Management", bg="#1e1e1e", expanded=True)
        path_mgmt_section.pack(fill=tk.X, padx=15, pady=15)
        
        path_btn_frame = tk.Frame(path_mgmt_section.content, bg="#1e1e1e")
        path_btn_frame.pack(fill=tk.X, padx=15, pady=15)
        
        self.save_btn = ModernButton(path_btn_frame, text="💾 Save Path", style="primary", command=self._save_path)
        self.save_btn.pack(side=tk.LEFT, padx=8, pady=8, fill=tk.X, expand=True)
        
        self.load_btn = ModernButton(path_btn_frame, text="📂 Load Path", style="primary", command=self._load_path)
        self.load_btn.pack(side=tk.LEFT, padx=8, pady=8, fill=tk.X, expand=True)
        
        self.clear_btn = ModernButton(path_btn_frame, text="🗑 Clear Path", style="warning", command=self._clear)
        self.clear_btn.pack(side=tk.LEFT, padx=8, pady=8, fill=tk.X, expand=True)
        
        # Path Info Section with improved display
        path_info_section = CollapsibleSection(path_content, "ℹ️ Path Information", bg="#1e1e1e", expanded=True)
        path_info_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        info_display = tk.Frame(path_info_section.content, bg="#1e1e1e")
        info_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.path_info_label = tk.Label(
            info_display,
            text="No path loaded",
            font=("Segoe UI", 11),
            bg="#1e1e1e",
            fg="#e0e0e0",
            justify=tk.LEFT,
            anchor=tk.NW,
            wraplength=600,
        )
        self.path_info_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            path_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        path_canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _setup_settings_tab(self) -> None:
        """Settings tab - All application settings with improved organization."""
        settings_frame = self.tabbed_ui.add_tab("Settings", "⚙️")
        
        # Use grid layout for better organization
        settings_frame.grid_rowconfigure(0, weight=1)
        settings_frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable content
        settings_canvas = tk.Canvas(settings_frame, bg="#0f0f0f", highlightthickness=0)
        settings_scrollbar = tk.Scrollbar(settings_frame, orient=tk.VERTICAL, command=settings_canvas.yview)
        settings_content = tk.Frame(settings_canvas, bg="#0f0f0f")
        
        settings_content.bind("<Configure>", lambda e: settings_canvas.configure(scrollregion=settings_canvas.bbox("all")))
        settings_canvas.create_window((0, 0), window=settings_content, anchor="nw")
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        
        settings_canvas.grid(row=0, column=0, sticky="nsew")
        settings_scrollbar.grid(row=0, column=1, sticky="ns")
        settings_frame.grid_columnconfigure(0, weight=1)
        
        # Prediction Settings Section
        prediction_section = CollapsibleSection(settings_content, "🔮 Position Prediction", bg="#1e1e1e", expanded=True)
        prediction_section.pack(fill=tk.X, padx=15, pady=15)
        
        delay_container = tk.Frame(prediction_section.content, bg="#1e1e1e")
        delay_container.pack(fill=tk.X, padx=15, pady=15)
        tk.Label(delay_container, text="Prediction Delay:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        delay_control = tk.Frame(delay_container, bg="#1e1e1e")
        delay_control.pack(fill=tk.X, pady=5)
        self.delay_var = tk.IntVar(value=100)
        delay_slider = ModernScale(
            delay_control,
            from_=0,
            to=300,
            orient=tk.HORIZONTAL,
            variable=self.delay_var,
            command=self._on_delay_change,
        )
        delay_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.delay_label = tk.Label(
            delay_control,
            text="100ms",
            bg="#1e1e1e",
            fg="#00d4aa",
            font=("Segoe UI", 10, "bold"),
            width=8,
        )
        self.delay_label.pack(side=tk.LEFT, padx=10)
        
        self.prediction_var = tk.BooleanVar(value=True)
        prediction_check = ModernCheckbutton(
            prediction_section.content,
            text="Enable Position Prediction",
            variable=self.prediction_var,
            command=self._on_setting_change,
        )
        prediction_check.pack(anchor=tk.W, padx=15, pady=10)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        settings_canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _setup_monitoring_tab(self) -> None:
        """Monitoring tab - Status and debug information with improved organization."""
        monitoring_frame = self.tabbed_ui.add_tab("Monitoring", "📊")
        
        # Use grid layout for better organization
        monitoring_frame.grid_rowconfigure(0, weight=1)
        monitoring_frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable content
        monitoring_canvas = tk.Canvas(monitoring_frame, bg="#0f0f0f", highlightthickness=0)
        monitoring_scrollbar = tk.Scrollbar(monitoring_frame, orient=tk.VERTICAL, command=monitoring_canvas.yview)
        monitoring_content = tk.Frame(monitoring_canvas, bg="#0f0f0f")
        
        monitoring_content.bind("<Configure>", lambda e: monitoring_canvas.configure(scrollregion=monitoring_canvas.bbox("all")))
        monitoring_canvas.create_window((0, 0), window=monitoring_content, anchor="nw")
        monitoring_canvas.configure(yscrollcommand=monitoring_scrollbar.set)
        
        monitoring_canvas.grid(row=0, column=0, sticky="nsew")
        monitoring_scrollbar.grid(row=0, column=1, sticky="ns")
        monitoring_frame.grid_columnconfigure(0, weight=1)
        
        # Connection Status Section
        status_section = CollapsibleSection(monitoring_content, "📡 Connection Status", bg="#1e1e1e", expanded=True)
        status_section.pack(fill=tk.X, padx=15, pady=15)
        
        status_display = tk.Frame(status_section.content, bg="#1e1e1e")
        status_display.pack(fill=tk.X, padx=15, pady=15)
        
        self.monitoring_status_label = StatusLabel(status_display, text="⚪ Not Connected", fg="#9e9e9e")
        self.monitoring_status_label.pack(fill=tk.X, padx=10, pady=10)
        
        # Robot Positions Section
        positions_section = CollapsibleSection(monitoring_content, "📍 Robot Positions", bg="#1e1e1e", expanded=True)
        positions_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        positions_display = tk.Frame(positions_section.content, bg="#1e1e1e")
        positions_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.positions_label = tk.Label(
            positions_display,
            text="Position: Not tracking",
            font=("Segoe UI", 11),
            bg="#1e1e1e",
            fg="#00d4aa",
            justify=tk.LEFT,
            anchor=tk.NW,
            wraplength=700,
        )
        self.positions_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Debug Info Section
        debug_section = CollapsibleSection(monitoring_content, "🐛 Debug Information", bg="#1e1e1e", expanded=True)
        debug_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        debug_display = tk.Frame(debug_section.content, bg="#1e1e1e")
        debug_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.debug_label = tk.Label(
            debug_display,
            text=self._get_debug_info(),
            font=("Segoe UI", 10),
            bg="#1e1e1e",
            fg="#e0e0e0",
            justify=tk.LEFT,
            anchor=tk.NW,
            wraplength=700,
        )
        self.debug_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            monitoring_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        monitoring_canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _update_robot_list_display(self) -> None:
        """Update the robot list display in Robots tab."""
        # Clear existing widgets
        for widget in self.robot_list_frame.winfo_children():
            widget.destroy()
        
        # Header
        header = tk.Frame(self.robot_list_frame, bg="#2d2d2d")
        header.pack(fill=tk.X, pady=2)
        tk.Label(header, text="Name", bg="#2d2d2d", fg="#00d4aa", font=("Segoe UI", 10, "bold"), width=15).pack(side=tk.LEFT, padx=5)
        tk.Label(header, text="Type", bg="#2d2d2d", fg="#00d4aa", font=("Segoe UI", 10, "bold"), width=10).pack(side=tk.LEFT, padx=5)
        tk.Label(header, text="Status", bg="#2d2d2d", fg="#00d4aa", font=("Segoe UI", 10, "bold"), width=15).pack(side=tk.LEFT, padx=5)
        
        # Robot rows
        for name, proxy in self.robots.items():
            row = tk.Frame(self.robot_list_frame, bg="#1e1e1e")
            row.pack(fill=tk.X, pady=2)
            
            is_active = name == self.active_robot
            fg_color = "#ffffff" if is_active else "#e0e0e0"
            
            tk.Label(row, text=name, bg="#1e1e1e", fg=fg_color, font=("Segoe UI", 10), width=15).pack(side=tk.LEFT, padx=5)
            tk.Label(row, text=proxy.robot_type, bg="#1e1e1e", fg=fg_color, font=("Segoe UI", 10), width=10).pack(side=tk.LEFT, padx=5)
            
            # Status
            with self._state_lock:
                is_following = name in self.follower_states
            status_text = "Following" if is_following else "Idle"
            status_color = "#00d4aa" if is_following else "#9e9e9e"
            tk.Label(row, text=status_text, bg="#1e1e1e", fg=status_color, font=("Segoe UI", 10), width=15).pack(side=tk.LEFT, padx=5)
            
            # Select button
            if not is_active:
                select_btn = ModernButton(row, text="Select", style="secondary", command=lambda n=name: self._select_robot(n))
                select_btn.config(font=("Segoe UI", 8))
                select_btn.pack(side=tk.RIGHT, padx=5)

    def _setup_services(self) -> None:
        self.path_service = PathService(self.canvas, self._world_to_canvas, self._canvas_to_world, color_provider=lambda r: self.robot_colors.get(r))
        # Sync existing colors to path service
        for rname, color in self.robot_colors.items():
            try:
                self.path_service.set_path_color(rname, color, redraw=False)
            except Exception:
                pass
        self.recording_service = RecordingService(
            self.backend_controller,
            self,
            self.robots[self.active_robot],
            self.canvas,
            self._world_to_canvas,
        )
        self.recording_service.on_recording_start = self._on_recording_start
        self.recording_service.on_recording_stop = self._on_recording_stop
        self.recording_service.on_position_recorded = self._on_position_recorded
        self.recording_service.set_joystick_enabled(False)

    # ------------------------------------------------------------------
    # Robot management
    # ------------------------------------------------------------------

    def _select_robot(self, robot_name: str) -> None:
        if robot_name not in self.robots:
            return
        self.robot_var.set(robot_name)
        self._on_robot_change(robot_name)
        self._update_robot_list_display()

    def _refresh_robot_dropdown(self) -> None:
        menu = self.robot_dropdown["menu"]
        menu.delete(0, "end")
        for name in self.robots.keys():
            menu.add_command(label=name, command=lambda value=name: self._select_robot(value))

    def _handle_add_robot(self) -> None:
        name = self.add_robot_name_var.get().strip()
        umh_id = self.add_robot_umh_var.get().strip()
        robot_type = self.add_robot_type_var.get().strip().lower() or "real"

        if not name:
            messagebox.showwarning("Add Robot", "Please provide a robot name.")
            return
        if name in self.robots:
            messagebox.showwarning("Add Robot", f"Robot '{name}' already exists.")
            return
        if robot_type == "real" and not umh_id:
            messagebox.showwarning("Add Robot", "Please provide UMH ID for real robots.")
            return

        robot_config = {
            "name": name,
            "type": robot_type,
            "umh_id": umh_id if robot_type == "real" else None,
            "cmd_vel_topic": f"/{name}/cmd_vel" if robot_type == "real" else None,
        }

        payload = {"type": "add_robot", "data": robot_config}
        self.udp_client.send(payload)
        ack = self.udp_client.wait_for_ack("add_robot", timeout=1.0)
        if not ack:
            messagebox.showwarning("Add Robot", "No confirmation from backend. Robot may not have been added.")

        self.config_loader.upsert_robot(name, robot_config)
        # Reload from loader to capture auto-assigned color
        updated_cfg = self.config_loader.get_robot_by_name(name) or robot_config
        self.robot_configs[name] = updated_cfg
        self.robots[name] = RobotStateProxy(self, name, robot_type)
        self.racing_configs[name] = RacingConfig(name)
        # Track color
        self.robot_colors[name] = updated_cfg.get("color", "#00aaff")
        self.path_service.set_path_color(name, self.robot_colors[name], redraw=False)
        with self._state_lock:
            self.robot_positions[name] = (0.0, 0.0, 0.0)

        self._refresh_robot_dropdown()
        self._select_robot(name)
        self._update_robot_list_display()
        messagebox.showinfo("Add Robot", f"Robot '{name}' added. Use set path to start tracking.")

    # ------------------------------------------------------------------
    # Backend communication & scheduling
    # ------------------------------------------------------------------

    def _auto_connect(self) -> None:
        self._connect()

    def _connect(self) -> None:
        self.status_label.config(text="🟡 Connecting to backend...", fg="#ffaa00")
        self.root.update()
        self.udp_client.start()
        self._sync_parameters_with_backend()
        self.tracking_active = True
        self.emergency_btn.config(state=tk.NORMAL)
        self._update_position()
        self._check_connection_status()

    def _check_connection_status(self) -> None:
        if not self.tracking_active:
            return
        status = self.udp_client.get_connection_status()
        connected = status.get("controlled_robots", []) if status else []
        num_real = len([r for r in self.robots.values() if r.robot_type == "real"])
        num_dummy = len([r for r in self.robots.values() if r.robot_type == "dummy"])

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
        
        self.status_label.config(text=text, fg=color)
        if hasattr(self, 'monitoring_status_label'):
            self.monitoring_status_label.config(text=text, fg=color)
        
        self.root.after(500, self._check_connection_status)

    def _on_backend_message(self, message: Dict) -> None:
        msg_type = message.get("type")
        data = message.get("data", {})
        if msg_type == "robot_states" and isinstance(data, dict):
            with self._state_lock:
                self.robot_states = data
                for name, state in data.items():
                    self.robot_positions[name] = (
                        state.get("x", 0.0),
                        state.get("y", 0.0),
                        state.get("yaw", 0.0),
                    )
        elif msg_type == "path_following_state" and isinstance(data, dict):
            with self._state_lock:
                self.follower_states = data
        elif msg_type == "connection_status" and isinstance(data, dict):
            with self._state_lock:
                self.connection_status = data
        elif msg_type == "error":
            messagebox.showwarning("Backend", str(data.get("message", data)))

    # ------------------------------------------------------------------
    # Mode switching & canvas interaction
    # ------------------------------------------------------------------

    def _update_mode_buttons(self) -> None:
        for mode_id, button in self.mode_buttons.items():
            if mode_id == self.current_mode:
                button.config(bg="#00d4aa", fg="#000000", relief=tk.FLAT)
            else:
                button.config(bg="#424242", fg="#ffffff", relief=tk.FLAT)

    def _switch_mode(self, mode: str) -> None:
        if self.recording_service.is_recording and mode != self.MODE_RECORD:
            self._stop_recording()
        self.current_mode = mode
        self._update_mode_buttons()
        if mode == self.MODE_CLICK:
            self.cmd_label.config(text=f"📍 {self.active_robot}: Click to add waypoints", fg="#fff")
            self.canvas.config(cursor="")
            self.joystick_container.grid_remove()
            self.recording_service.set_joystick_enabled(False)
        elif mode == self.MODE_DRAW:
            self.cmd_label.config(text=f"✏️ {self.active_robot}: Drag to draw path", fg="#00aaff")
            self.canvas.config(cursor="pencil")
            self.joystick_container.grid_remove()
            self.recording_service.set_joystick_enabled(False)
        else:
            self.cmd_label.config(text=f"🎮 {self.active_robot}: Use joystick", fg="#ff6600")
            self.canvas.config(cursor="")
            # Show joystick container using grid
            self.joystick_container.grid(row=1, column=1, sticky="ns", padx=(10, 0))
            self.joystick_container.grid_propagate(False)
            self.recording_service.set_joystick_enabled(True)

    def _world_to_canvas(self, x_m: float, y_m: float):
        x = x_m * self.scale + self.canvas_width / 2
        y = y_m * self.scale + self.canvas_height / 2
        return x, y

    def _canvas_to_world(self, x: float, y: float):
        x_m = (x - self.canvas_width / 2) / self.scale
        y_m = (y - self.canvas_height / 2) / self.scale
        return x_m, y_m

    def _on_canvas_click(self, event):
        if not self.tracking_active or self.current_mode == self.MODE_RECORD:
            return
        x, y = event.x, event.y
        if self.current_mode == self.MODE_DRAW:
            self.is_drawing = True
            self.last_draw_point = (x, y)
            self.path_service.add_waypoint(self.active_robot, x, y, "draw")
        else:
            self.path_service.add_waypoint(self.active_robot, x, y, "click")
        self._update_path_status()

    def _on_canvas_drag(self, event):
        if self.current_mode != self.MODE_DRAW or not self.is_drawing or not self.tracking_active:
            return
        x, y = event.x, event.y
        if self.last_draw_point is not None:
            dx = x - self.last_draw_point[0]
            dy = y - self.last_draw_point[1]
            dist = math.sqrt(dx ** 2 + dy ** 2)
            if dist >= self.draw_sample_distance:
                self.path_service.add_waypoint(self.active_robot, x, y, "draw")
                self.last_draw_point = (x, y)
                self._update_path_status()

    def _on_canvas_release(self, event):
        if self.current_mode == self.MODE_DRAW:
            self.is_drawing = False
            self.last_draw_point = None

    # ------------------------------------------------------------------
    # Path and recording management
    # ------------------------------------------------------------------

    def _update_path_status(self) -> None:
        info = self.path_service.get_path_info(self.active_robot)
        mode_name = "📍 Click" if self.current_mode == self.MODE_CLICK else "✏️ Draw"
        total_paths = sum(1 for r in self.robots if self.path_service.has_path(r))
        status_text = f"{mode_name} | {self.active_robot}: {info['num_waypoints']} pts"
        if total_paths > 1:
            status_text += f" | {total_paths} robots have paths"
        self.cmd_label.config(text=status_text)
        
        # Update path info in Path Planning tab
        if hasattr(self, 'path_info_label'):
            path_info = f"Active Robot: {self.active_robot}\n"
            path_info += f"Waypoints: {info['num_waypoints']}\n"
            path_info += f"Is Recorded: {'Yes' if info['is_recorded'] else 'No'}\n"
            path_info += f"Total Robots with Paths: {total_paths}"
            self.path_info_label.config(text=path_info)
        
        self._update_button_states()

    def _toggle_recording(self) -> None:
        if not self.tracking_active or not self.backend_controller.connected:
            messagebox.showwarning("Recording", "Please connect to the backend first.")
            return
        if self.recording_service.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        self.path_service.clear_path(self.active_robot)
        if self.recording_service.start_recording():
            self.record_btn.config(text="⏹ STOP RECORDING", style="success")
            self.cmd_label.config(text=f"🎮 Recording {self.active_robot}...", fg="#f44336")
            self.save_btn.config(state=tk.DISABLED)
            self.load_btn.config(state=tk.DISABLED)

    def _stop_recording(self) -> None:
        recorded = self.recording_service.stop_recording()
        self.record_btn.config(text="⏺ START RECORDING", style="danger")
        self.save_btn.config(state=tk.NORMAL)
        self.load_btn.config(state=tk.NORMAL)
        if recorded:
            self.path_service.set_recorded_path(self.active_robot, recorded)
            self.cmd_label.config(
                text=f"🎮 {self.active_robot}: {len(recorded)} points recorded",
                fg="#00ff88",
            )
            self._update_button_states()
        else:
            self.cmd_label.config(text="🎮 No motion recorded", fg="#FFA500")

    def _on_recording_start(self):
        pass

    def _on_recording_stop(self):
        pass

    def _on_position_recorded(self, count: int) -> None:
        self.cmd_label.config(text=f"🎮 Recording {self.active_robot}... {count} points", fg="#f44336")

    def _save_path(self) -> None:
        self.path_service.save_path(self.active_robot)
        self._update_path_status()

    def _load_path(self) -> None:
        if self.path_service.load_path(self.active_robot):
            info = self.path_service.get_path_info(self.active_robot)
            self.cmd_label.config(
                text=f"✓ {self.active_robot}: {info['num_waypoints']} waypoints loaded",
                fg="#00ff88",
            )
            self._update_button_states()
            self._update_path_status()

    def _clear(self) -> None:
        self.udp_client.send({"type": "clear_path", "data": {"robot": self.active_robot}})
        self.path_service.clear_path(self.active_robot)
        self.is_drawing = False
        self.last_draw_point = None
        self._update_button_states()
        self._update_path_status()
        if self.current_mode == self.MODE_CLICK:
            self.cmd_label.config(text=f"📍 {self.active_robot}: Click to add waypoints", fg="#fff")
        elif self.current_mode == self.MODE_DRAW:
            self.cmd_label.config(text=f"✏️ {self.active_robot}: Drag to draw path", fg="#00aaff")
        else:
            self.cmd_label.config(text=f"🎮 {self.active_robot}: Use joystick", fg="#ff6600")

    # ------------------------------------------------------------------
    # Backend control methods
    # ------------------------------------------------------------------

    def _push_path_to_backend(self, robot_name: str, waypoints: list[tuple[float, float]]) -> None:
        payload = {
            "type": "set_path",
            "data": {
                "robot": robot_name,
                "waypoints": [list(point) for point in waypoints],
            },
        }
        self.udp_client.send(payload)

    def _send_racing_config(self, robot_name: str) -> None:
        cfg = self.racing_configs[robot_name]
        payload = {
            "type": "set_racing_config",
            "data": {
                "robot": robot_name,
                "offset": cfg.lateral_offset,
                "speed": cfg.speed_multiplier,
                "loop": cfg.loop_path,
            },
        }
        self.udp_client.send(payload)

    def _start(self) -> None:
        cfg = self.racing_configs[self.active_robot]
        info = self.path_service.get_path_info(self.active_robot, cfg.loop_path)
        if info["num_waypoints"] == 0:
            return
        waypoints = info["waypoints_meters"]
        self._push_path_to_backend(self.active_robot, waypoints)
        self._send_racing_config(self.active_robot)
        self.udp_client.send({"type": "start_path", "data": {"robot": self.active_robot}})
        self.cmd_label.config(text=f"▶ {self.active_robot} following path...", fg="#00ff88")
        self._update_button_states()
        self._update_robot_list_display()

    def _start_all(self) -> None:
        started = 0
        for name in self.robots.keys():
            cfg = self.racing_configs[name]
            info = self.path_service.get_path_info(name, cfg.loop_path)
            if info["num_waypoints"] == 0:
                continue
            waypoints = info["waypoints_meters"]
            self._push_path_to_backend(name, waypoints)
            self._send_racing_config(name)
            started += 1
        if started:
            self.udp_client.send({"type": "start_all_paths", "data": {}})
            self.cmd_label.config(text=f"▶ {started} robots following paths...", fg="#00ff88")
        self._update_button_states()
        self._update_robot_list_display()

    def _stop(self) -> None:
        self.udp_client.send({"type": "stop_path", "data": {"robot": self.active_robot}})
        self.cmd_label.config(text=f"⏸ {self.active_robot} stopped", fg="#ffaa00")
        self._update_button_states()
        self._update_robot_list_display()

    def _stop_all(self) -> None:
        self.udp_client.send({"type": "stop_all", "data": {}})
        self.cmd_label.config(text="⏸ All stopped", fg="#ffaa00")
        self._update_button_states()
        self._update_robot_list_display()

    def _emergency(self) -> None:
        self.udp_client.send({"type": "emergency_stop", "data": {}})
        self.cmd_label.config(text="🛑 EMERGENCY", fg="#f44336")

    def _update_button_states(self) -> None:
        with self._state_lock:
            active_followers = set(self.follower_states.keys())
        has_path = self.path_service.has_path(self.active_robot)
        is_following = self.active_robot in active_followers
        # Keep Start enabled as long as there is a path
        self.start_btn.config(state=tk.NORMAL if has_path else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if is_following else tk.DISABLED)
        any_has_path = any(self.path_service.has_path(r) for r in self.robots.keys())
        any_following = bool(active_followers)
        self.start_all_btn.config(state=tk.NORMAL if any_has_path else tk.DISABLED)
        self.stop_all_btn.config(state=tk.NORMAL if any_following else tk.DISABLED)

    def _on_offset_change(self, value):
        offset = float(value)
        cfg = self.racing_configs[self.active_robot]
        cfg.set_offset(offset)
        self.offset_label.config(text=f"{offset:.2f}m")
        self._send_racing_config(self.active_robot)

    def _on_speed_change(self, value):
        speed = float(value)
        cfg = self.racing_configs[self.active_robot]
        cfg.set_speed_multiplier(speed)
        self.speed_label.config(text=f"{speed:.1f}x")
        self._send_racing_config(self.active_robot)

    def _on_loop_change(self):
        loop = self.loop_var.get()
        cfg = self.racing_configs[self.active_robot]
        cfg.set_loop(loop)
        self._send_racing_config(self.active_robot)

    def _on_delay_change(self, value):
        self.estimated_delay_ms = int(value)
        self.delay_label.config(text=f"{self.estimated_delay_ms}ms")
        self._sync_parameters_with_backend()

    def _on_setting_change(self):
        self.use_prediction = self.prediction_var.get()
        self._sync_parameters_with_backend()

    def _sync_parameters_with_backend(self) -> None:
        payload = {
            "type": "set_parameters",
            "data": {
                "use_prediction": self.prediction_var.get(),
                "estimated_delay_ms": self.delay_var.get(),
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
            },
        }
        self.udp_client.send(payload)

    # ------------------------------------------------------------------
    # Robot change & updates
    # ------------------------------------------------------------------

    def _on_robot_change(self, robot_name: str) -> None:
        self.active_robot = robot_name
        self.backend_controller.set_default_robot(robot_name)
        self.recording_service.robot = self.robots[robot_name]
        cfg = self.racing_configs[robot_name]
        self.offset_var.set(cfg.lateral_offset)
        self.speed_var.set(cfg.speed_multiplier)
        self.loop_var.set(cfg.loop_path)
        self.offset_label.config(text=f"{cfg.lateral_offset:.2f}m")
        self.speed_label.config(text=f"{cfg.speed_multiplier:.1f}x")
        # Update robot config section title
        if hasattr(self, 'robot_config_section'):
            self.robot_config_section.title_label.config(text=f"⚙️ {robot_name} Config")
        self._apply_active_robot_theme()
        self._update_button_states()
        self._update_path_status()

    def _update_position(self) -> None:
        if not self.tracking_active:
            return
        self._draw_robots()
        x, y, yaw = self.get_robot_position(self.active_robot)
        yaw_deg = math.degrees(yaw)
        robot_type = self.robots[self.active_robot].robot_type
        prefix = "🤖" if robot_type == "real" else "🎮"
        
        # Update positions label in Monitoring tab
        if hasattr(self, 'positions_label'):
            positions_text = f"{prefix} {self.active_robot}: ({x:6.3f}, {y:6.3f})m | {yaw_deg:6.1f}°\n\n"
            for name, proxy in self.robots.items():
                if name != self.active_robot:
                    rx, ry, ryaw = self.get_robot_position(name)
                    rprefix = "🤖" if proxy.robot_type == "real" else "🎮"
                    positions_text += f"{rprefix} {name}: ({rx:6.3f}, {ry:6.3f})m | {math.degrees(ryaw):6.1f}°\n"
            self.positions_label.config(text=positions_text)
        
        self.debug_label.config(text=self._get_debug_info())
        if self.recording_service.joystick_control_active:
            joy_x, joy_y = self.joystick.get_values()
            self.recording_service.process_joystick_input(joy_x, joy_y)
        self.root.after(50, self._update_position)

    def _draw_robots(self) -> None:
        for visual in list(self.robot_visuals.values()):
            self.canvas.delete(visual)
        self.robot_visuals.clear()
        self.canvas.delete("robot_arrow")
        self.canvas.delete("robot_label")

        with self._state_lock:
            positions = dict(self.robot_positions)
            followers = set(self.follower_states.keys())

        for name, proxy in self.robots.items():
            x_m, y_m, yaw = positions.get(name, (0.0, 0.0, 0.0))
            x, y = self._world_to_canvas(x_m, y_m)
            is_active = name == self.active_robot
            is_dummy = proxy.robot_type == "dummy"
            has_path = self.path_service.has_path(name)
            is_following = name in followers

            size = 22 if is_active else 16
            base_color = self.robot_colors.get(name, "#00aaff")
            # Use a lighter/darker version for fill, white outline for visibility
            try:
                r = int(base_color[1:3], 16)
                g = int(base_color[3:5], 16)
                b = int(base_color[5:7], 16)
                # Make fill slightly lighter/softer
                fill_r = min(255, int(r * 0.7))
                fill_g = min(255, int(g * 0.7))
                fill_b = min(255, int(b * 0.7))
                fill_color = f"#{fill_r:02x}{fill_g:02x}{fill_b:02x}"
            except Exception:
                fill_color = base_color
            
            # Outline color - white for active, darker for inactive
            if is_active:
                outline_color = "#ffffff"
            else:
                # Darker version of base color for outline
                try:
                    outline_r = max(0, int(r * 0.5))
                    outline_g = max(0, int(g * 0.5))
                    outline_b = max(0, int(b * 0.5))
                    outline_color = f"#{outline_r:02x}{outline_g:02x}{outline_b:02x}"
                except Exception:
                    outline_color = "#333333"
            
            if is_following:
                outline_width = 5 if is_active else 3
            elif has_path:
                outline_width = 4 if is_active else 2
            else:
                outline_width = 3 if is_active else 2

            visual = self.canvas.create_oval(
                x - size,
                y - size,
                x + size,
                y + size,
                fill=fill_color,
                outline=outline_color,
                width=outline_width,
            )
            self.robot_visuals[name] = visual

            arrow_len = size * 1.5
            arrow_x = x + arrow_len * math.cos(yaw)
            arrow_y = y + arrow_len * math.sin(yaw)
            self.canvas.create_line(
                x,
                y,
                arrow_x,
                arrow_y,
                fill=base_color,
                width=3 if is_active else 2,
                arrow=tk.LAST,
                tags="robot_arrow",
            )

            label_text = name if is_active else name[:6]
            self.canvas.create_text(
                x,
                y - size - 10,
                text=label_text,
                fill=base_color if is_active else "#888",
                font=("Arial", 9 if is_active else 7, "bold"),
                tags="robot_label",
            )

    def _apply_active_robot_theme(self) -> None:
        """Apply the active robot's color theme to UI elements."""
        if not hasattr(self, 'active_robot') or not hasattr(self, 'robot_colors'):
            return
        
        color = self.robot_colors.get(self.active_robot, "#00aaff")
        # Determine readable text color
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
        except Exception:
            r, g, b = 0, 170, 255
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        fg = "#000000" if luminance > 140 else "#ffffff"
        active_bg = color
        
        # Apply to main control buttons using set_custom_color method
        buttons_to_update = []
        if hasattr(self, 'start_btn'):
            buttons_to_update.append(self.start_btn)
        if hasattr(self, 'stop_btn'):
            buttons_to_update.append(self.stop_btn)
        if hasattr(self, 'emergency_btn'):
            buttons_to_update.append(self.emergency_btn)
        
        for btn in buttons_to_update:
            try:
                if hasattr(btn, 'set_custom_color'):
                    btn.set_custom_color(active_bg, fg)
                else:
                    # Fallback for non-ModernButton widgets
                    btn.config(
                        bg=active_bg, 
                        fg=fg, 
                        activebackground=active_bg, 
                        activeforeground=fg,
                        disabledbackground=active_bg,
                        disabledforeground=fg
                    )
            except Exception as e:
                # Silently fail - buttons might not be initialized yet
                pass
        
        # Update command label accent color
        if hasattr(self, 'cmd_label'):
            try:
                self.cmd_label.config(fg=color)
            except Exception:
                pass

    def _get_debug_info(self) -> str:
        x, y, yaw = self.get_robot_position(self.active_robot)
        yaw_deg = math.degrees(yaw)
        follower = self.follower_states.get(self.active_robot)
        lines = [
            f"Current Location:  ({x:6.3f}m, {y:6.3f}m)",
            f"Current Rotation:  {yaw_deg:7.2f}°",
        ]
        if follower:
            lines.append(
                f"Waypoint {follower.get('waypoint_index', 0)+1}/{follower.get('total_waypoints', 0)}"
            )
            dist = follower.get("distance_to_target")
            if dist is not None:
                lines.append(f"Distance to Target: {dist:.3f}m")
            throttle = follower.get("throttle")
            if throttle is not None:
                lines.append(f"Throttle: {throttle:.2f}")
        else:
            lines.append("Follower State: N/A")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Miscellaneous utilities
    # ------------------------------------------------------------------

    def _on_window_resize(self, event) -> None:
        """Handle window resize with improved canvas resizing logic."""
        if event.widget != self.root:
            return
        
        # Get actual window dimensions
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        
        # Account for tab bar, status bar, and padding
        status_bar_height = 60
        tab_bar_height = 55
        padding = 40
        
        # Calculate available space
        left_panel_width = 360
        joystick_width = 320 if self.current_mode == self.MODE_RECORD else 0
        available_width = window_width - left_panel_width - joystick_width - padding
        available_height = window_height - status_bar_height - tab_bar_height - padding
        
        # Ensure minimum sizes
        if available_width < 400 or available_height < 300:
            return
        
        # Maintain aspect ratio but fill available space better
        aspect_ratio = 16 / 9
        target_aspect = available_width / available_height
        
        if target_aspect > aspect_ratio:
            # Window is wider than ideal - use height as constraint
            new_height = max(300, available_height)
            new_width = int(new_height * aspect_ratio)
        else:
            # Window is taller than ideal - use width as constraint
            new_width = max(400, available_width)
            new_height = int(new_width / aspect_ratio)
        
        # Only update if change is significant (reduces flicker)
        if abs(new_width - self.canvas_width) > 30 or abs(new_height - self.canvas_height) > 30:
            self.canvas_width = new_width
            self.canvas_height = new_height
            self.canvas.config(width=self.canvas_width, height=self.canvas_height)
            self.canvas.delete("grid", "origin")
            self.grid_helper.width = self.canvas_width
            self.grid_helper.height = self.canvas_height
            self.grid_helper.draw_grid()
            # Redraw paths and robots
            if self.robot_visuals:
                self._draw_robots()
            # Redraw paths for all robots
            for robot_name in self.robots.keys():
                if robot_name in self.path_service.robot_paths:
                    self.path_service._redraw_path(robot_name)

    def shutdown(self) -> None:
        print("\n[Controller] Shutting down...")
        if self.recording_service.is_recording:
            self.recording_service.stop_recording()
        self.udp_client.send({"type": "stop_all", "data": {}})
        self.udp_client.close()
        self.root.quit()
        print("[Controller] Complete")

    def run(self) -> None:
        print(f"\n[Controller] Starting with {len(self.robots)} robots")
        print("[Controller] Auto-connecting...\n")
        self.root.mainloop()


def main() -> None:
    try:
        app = RobotControllerApp()
        app.run()
    except KeyboardInterrupt:
        print("\n[Controller] Interrupted")
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"[Controller] Error: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
