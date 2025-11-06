#!/usr/bin/env python3
"""Hydra frontend controller application."""

from __future__ import annotations

import math
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

import tkinter as tk
from tkinter import messagebox

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

        for name, cfg in robot_config.items():
            robot_type = cfg.get("type", "real")
            self.robots[name] = RobotStateProxy(self, name, robot_type)
            self.racing_configs[name] = RacingConfig(name)

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
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.root = tk.Tk()
        self.root.title("🤖 Hydra Robot Swarm Controller")
        self.root.configure(bg="#0f0f0f")
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        main_container = tk.Frame(self.root, bg="#0f0f0f")
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        self._setup_left_panel(main_container)
        self._setup_right_panel(main_container)

    def _setup_left_panel(self, parent: tk.Widget) -> None:
        left_panel = tk.Frame(parent, bg="#1a1a1a", width=280)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_panel.pack_propagate(False)

        canvas = tk.Canvas(left_panel, bg="#1a1a1a", highlightthickness=0)
        scrollbar = tk.Scrollbar(left_panel, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#1a1a1a")

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._setup_robot_selector(scrollable_frame)
        self._setup_mode_selector(scrollable_frame)
        self._setup_settings(scrollable_frame)
        self._setup_status(scrollable_frame)
        self._setup_controls(scrollable_frame)
        self._setup_path_management(scrollable_frame)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

    def _setup_robot_selector(self, parent: tk.Widget) -> None:
        robot_frame = ModernFrame(parent, title="🤖 ROBOTS")
        robot_frame.pack(fill=tk.X, padx=10, pady=10)

        self.robot_var = tk.StringVar(value=self.active_robot)
        self.robot_dropdown = tk.OptionMenu(
            robot_frame,
            self.robot_var,
            *self.robots.keys(),
            command=lambda value: self._select_robot(value),
        )
        self.robot_dropdown.config(
            bg="#2a2a2a",
            fg="#fff",
            font=("Arial", 10),
            highlightthickness=0,
            activebackground="#00ff88",
        )
        self.robot_dropdown.pack(fill=tk.X, padx=8, pady=(8, 5))

        race_cfg_frame = tk.Frame(robot_frame, bg="#1a1a1a")
        race_cfg_frame.pack(fill=tk.X, padx=8, pady=5)

        tk.Label(
            race_cfg_frame,
            text="Offset:",
            bg="#1a1a1a",
            fg="#ccc",
            font=("Arial", 8),
        ).grid(row=0, column=0, sticky=tk.W)
        self.offset_var = tk.DoubleVar(value=0.0)
        offset_scale = ModernScale(
            race_cfg_frame,
            from_=-0.5,
            to=0.5,
            orient=tk.HORIZONTAL,
            variable=self.offset_var,
            command=self._on_offset_change,
            resolution=0.05,
        )
        offset_scale.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.offset_label = tk.Label(
            race_cfg_frame,
            text="0.0m",
            bg="#1a1a1a",
            fg="#00ff88",
            font=("Arial", 8),
            width=6,
        )
        self.offset_label.grid(row=0, column=2)

        tk.Label(
            race_cfg_frame,
            text="Speed:",
            bg="#1a1a1a",
            fg="#ccc",
            font=("Arial", 8),
        ).grid(row=1, column=0, sticky=tk.W, pady=(3, 0))
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_scale = ModernScale(
            race_cfg_frame,
            from_=0.3,
            to=1.5,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            command=self._on_speed_change,
            resolution=0.1,
        )
        speed_scale.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=(3, 0))
        self.speed_label = tk.Label(
            race_cfg_frame,
            text="1.0x",
            bg="#1a1a1a",
            fg="#00ff88",
            font=("Arial", 8),
            width=6,
        )
        self.speed_label.grid(row=1, column=2, pady=(3, 0))

        race_cfg_frame.columnconfigure(1, weight=1)

        self.loop_var = tk.BooleanVar(value=False)
        loop_check = ModernCheckbutton(
            robot_frame,
            text="Loop Circuit",
            variable=self.loop_var,
            command=self._on_loop_change,
        )
        loop_check.pack(anchor=tk.W, padx=8, pady=(3, 5))

        btn_frame = tk.Frame(robot_frame, bg="#1a1a1a")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
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

        add_frame = tk.LabelFrame(
            robot_frame,
            text="Add Robot",
            bg="#1a1a1a",
            fg="#00ff88",
            font=("Arial", 9, "bold"),
        )
        add_frame.pack(fill=tk.X, padx=8, pady=8)

        tk.Label(add_frame, text="Name", bg="#1a1a1a", fg="#ccc").grid(row=0, column=0, sticky=tk.W)
        self.add_robot_name_var = tk.StringVar()
        tk.Entry(add_frame, textvariable=self.add_robot_name_var, bg="#2a2a2a", fg="#fff").grid(
            row=0, column=1, sticky=tk.EW, padx=5, pady=2
        )

        tk.Label(add_frame, text="UMH ID", bg="#1a1a1a", fg="#ccc").grid(row=1, column=0, sticky=tk.W)
        self.add_robot_umh_var = tk.StringVar()
        tk.Entry(add_frame, textvariable=self.add_robot_umh_var, bg="#2a2a2a", fg="#fff").grid(
            row=1, column=1, sticky=tk.EW, padx=5, pady=2
        )

        tk.Label(add_frame, text="Type", bg="#1a1a1a", fg="#ccc").grid(row=2, column=0, sticky=tk.W)
        self.add_robot_type_var = tk.StringVar(value="real")
        type_menu = tk.OptionMenu(
            add_frame,
            self.add_robot_type_var,
            "real",
            "dummy",
        )
        type_menu.config(bg="#2a2a2a", fg="#fff", highlightthickness=0)
        type_menu.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)

        add_button = ModernButton(add_frame, text="➕ Add", style="primary", command=self._handle_add_robot)
        add_button.grid(row=3, column=0, columnspan=2, pady=6)

        add_frame.columnconfigure(1, weight=1)

    def _setup_mode_selector(self, parent: tk.Widget) -> None:
        mode_frame = ModernFrame(parent, title="🎯 MODE")
        mode_frame.pack(fill=tk.X, padx=10, pady=10)

        self.mode_buttons: Dict[str, tk.Button] = {}
        modes = [
            (self.MODE_CLICK, "📍 Click"),
            (self.MODE_DRAW, "✏️ Draw"),
            (self.MODE_RECORD, "🎮 Record"),
        ]
        for mode_id, label in modes:
            btn = ModernButton(
                mode_frame,
                text=label,
                style="secondary",
                command=lambda value=mode_id: self._switch_mode(value),
            )
            btn.pack(fill=tk.X, padx=5, pady=3)
            self.mode_buttons[mode_id] = btn
        self._update_mode_buttons()

    def _setup_settings(self, parent: tk.Widget) -> None:
        settings_frame = ModernFrame(parent, title="⚙️ SETTINGS")
        settings_frame.pack(fill=tk.X, padx=10, pady=10)

        delay_container = tk.Frame(settings_frame, bg="#1a1a1a")
        delay_container.pack(fill=tk.X, padx=8, pady=5)
        tk.Label(delay_container, text="Prediction Delay:", bg="#1a1a1a", fg="#ccc").pack(anchor=tk.W)
        delay_control = tk.Frame(delay_container, bg="#1a1a1a")
        delay_control.pack(fill=tk.X, pady=3)
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
            bg="#1a1a1a",
            fg="#00ff88",
            font=("Arial", 9, "bold"),
            width=6,
        )
        self.delay_label.pack(side=tk.LEFT, padx=5)

        self.prediction_var = tk.BooleanVar(value=True)
        prediction_check = ModernCheckbutton(
            settings_frame,
            text="Enable Position Prediction",
            variable=self.prediction_var,
            command=self._on_setting_change,
        )
        prediction_check.pack(anchor=tk.W, padx=8, pady=5)

    def _setup_status(self, parent: tk.Widget) -> None:
        status_frame = ModernFrame(parent, title="📡 STATUS")
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        self.status_label = StatusLabel(status_frame, text="⚪ Not Connected", fg="#888")
        self.status_label.pack(fill=tk.X, padx=8, pady=8)

    def _setup_controls(self, parent: tk.Widget) -> None:
        control_frame = ModernFrame(parent, title="🎮 CONTROLS")
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        self.start_btn = ModernButton(
            control_frame,
            text="▶ START PATH",
            style="success",
            command=self._start,
            state=tk.DISABLED,
        )
        self.start_btn.config(pady=12, font=("Arial", 11, "bold"))
        self.start_btn.pack(fill=tk.X, padx=5, pady=5)

        self.stop_btn = ModernButton(
            control_frame,
            text="⏸ STOP",
            style="warning",
            command=self._stop,
            state=tk.DISABLED,
        )
        self.stop_btn.config(pady=12, font=("Arial", 11, "bold"))
        self.stop_btn.pack(fill=tk.X, padx=5, pady=5)

        self.emergency_btn = ModernButton(
            control_frame,
            text="🛑 EMERGENCY STOP",
            style="danger",
            command=self._emergency,
            state=tk.DISABLED,
        )
        self.emergency_btn.config(pady=12, font=("Arial", 11, "bold"))
        self.emergency_btn.pack(fill=tk.X, padx=5, pady=5)

    def _setup_path_management(self, parent: tk.Widget) -> None:
        path_frame = ModernFrame(parent, title="📁 PATH")
        path_frame.pack(fill=tk.X, padx=10, pady=10)

        path_btn_frame = tk.Frame(path_frame, bg="#1a1a1a")
        path_btn_frame.pack(fill=tk.X, padx=5, pady=5)

        self.save_btn = ModernButton(path_btn_frame, text="💾", style="secondary", command=self._save_path, width=4)
        self.save_btn.config(font=("Arial", 10, "bold"))
        self.save_btn.pack(side=tk.LEFT, padx=2)

        self.load_btn = ModernButton(path_btn_frame, text="📂", style="secondary", command=self._load_path, width=4)
        self.load_btn.config(font=("Arial", 10, "bold"))
        self.load_btn.pack(side=tk.LEFT, padx=2)

        self.clear_btn = ModernButton(path_btn_frame, text="🗑 CLEAR", style="secondary", command=self._clear)
        self.clear_btn.config(font=("Arial", 10, "bold"))
        self.clear_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    def _setup_right_panel(self, parent: tk.Widget) -> None:
        right_container = tk.Frame(parent, bg="#0f0f0f")
        right_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_panel = tk.Frame(right_container, bg="#0f0f0f")
        self.canvas_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.cmd_label = tk.Label(
            self.canvas_panel,
            text="📍 Click mode: Click to add waypoints",
            font=("Arial", 11, "bold"),
            bg="#1a1a1a",
            fg="#fff",
            pady=8,
        )
        self.cmd_label.pack(fill=tk.X)

        canvas_container = tk.Frame(self.canvas_panel, bg="#1a1a1a", bd=2, relief=tk.GROOVE)
        canvas_container.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.canvas = tk.Canvas(
            canvas_container,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#0a0a0a",
            highlightthickness=0,
        )
        self.canvas.pack(padx=3, pady=3)

        self.grid_helper = CanvasGrid(self.canvas, self.scale, self.canvas_width, self.canvas_height)
        self.grid_helper.draw_grid()

        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        info_panel = tk.Frame(self.canvas_panel, bg="#1a1a1a", bd=2, relief=tk.GROOVE)
        info_panel.pack(fill=tk.X, pady=(5, 0))
        self.info_label = tk.Label(
            info_panel,
            text="Position: Not tracking",
            font=("Courier", 10),
            bg="#1a1a1a",
            fg="#00ff88",
            pady=8,
        )
        self.info_label.pack()

        debug_panel = tk.Frame(self.canvas_panel, bg="#1a1a1a", bd=2, relief=tk.GROOVE)
        debug_panel.pack(fill=tk.X, pady=(5, 0))
        tk.Label(
            debug_panel,
            text="📊 DEBUG INFO",
            font=("Arial", 9, "bold"),
            bg="#1a1a1a",
            fg="#00ff88",
        ).pack(pady=(5, 0))
        self.debug_label = tk.Label(
            debug_panel,
            text=self._get_debug_info(),
            font=("Courier", 8),
            bg="#1a1a1a",
            fg="#ccc",
            justify=tk.LEFT,
            pady=8,
        )
        self.debug_label.pack()

        self.joystick_container = tk.Frame(right_container, bg="#0f0f0f", width=300)
        joystick_frame = tk.LabelFrame(
            self.joystick_container,
            text="🕹️ JOYSTICK",
            font=("Arial", 10, "bold"),
            bg="#1a1a1a",
            fg="#00ff88",
            bd=2,
            relief=tk.GROOVE,
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
        self.record_btn.config(pady=12, font=("Arial", 11, "bold"))
        self.record_btn.pack(fill=tk.X, padx=15, pady=(0, 15))

    def _setup_services(self) -> None:
        self.path_service = PathService(self.canvas, self._world_to_canvas, self._canvas_to_world)
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
    # Robot addition helpers
    # ------------------------------------------------------------------

    def _select_robot(self, robot_name: str) -> None:
        if robot_name not in self.robots:
            return
        self.robot_var.set(robot_name)
        self._on_robot_change(robot_name)

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
        self.robot_configs[name] = robot_config
        self.robots[name] = RobotStateProxy(self, name, robot_type)
        self.racing_configs[name] = RacingConfig(name)
        with self._state_lock:
            self.robot_positions[name] = (0.0, 0.0, 0.0)

        self._refresh_robot_dropdown()
        self._select_robot(name)
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
                button.config(bg="#00ff88", fg="#000000", relief=tk.RAISED)
            else:
                button.config(bg="#2a2a2a", fg="#ffffff", relief=tk.FLAT)

    def _switch_mode(self, mode: str) -> None:
        if self.recording_service.is_recording and mode != self.MODE_RECORD:
            self._stop_recording()
        self.current_mode = mode
        self._update_mode_buttons()
        if mode == self.MODE_CLICK:
            self.cmd_label.config(text=f"📍 {self.active_robot}: Click to add waypoints", fg="#fff")
            self.canvas.config(cursor="")
            self.joystick_container.pack_forget()
            self.recording_service.set_joystick_enabled(False)
        elif mode == self.MODE_DRAW:
            self.cmd_label.config(text=f"✏️ {self.active_robot}: Drag to draw path", fg="#00aaff")
            self.canvas.config(cursor="pencil")
            self.joystick_container.pack_forget()
            self.recording_service.set_joystick_enabled(False)
        else:
            self.cmd_label.config(text=f"🎮 {self.active_robot}: Use joystick", fg="#ff6600")
            self.canvas.config(cursor="")
            self.joystick_container.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0), before=self.canvas_panel)
            self.joystick_container.pack_propagate(False)
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
            self.start_btn.config(state=tk.DISABLED)
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

    def _load_path(self) -> None:
        if self.path_service.load_path(self.active_robot):
            info = self.path_service.get_path_info(self.active_robot)
            self.cmd_label.config(
                text=f"✓ {self.active_robot}: {info['num_waypoints']} waypoints loaded",
                fg="#00ff88",
            )
            self._update_button_states()

    def _clear(self) -> None:
        self.udp_client.send({"type": "clear_path", "data": {"robot": self.active_robot}})
        self.path_service.clear_path(self.active_robot)
        self.is_drawing = False
        self.last_draw_point = None
        self._update_button_states()
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

    def _stop(self) -> None:
        self.udp_client.send({"type": "stop_path", "data": {"robot": self.active_robot}})
        self.cmd_label.config(text=f"⏸ {self.active_robot} stopped", fg="#ffaa00")
        self._update_button_states()

    def _stop_all(self) -> None:
        self.udp_client.send({"type": "stop_all", "data": {}})
        self.cmd_label.config(text="⏸ All stopped", fg="#ffaa00")
        self._update_button_states()

    def _emergency(self) -> None:
        self.udp_client.send({"type": "emergency_stop", "data": {}})
        self.cmd_label.config(text="🛑 EMERGENCY", fg="#f44336")

    def _update_button_states(self) -> None:
        with self._state_lock:
            active_followers = set(self.follower_states.keys())
        has_path = self.path_service.has_path(self.active_robot)
        is_following = self.active_robot in active_followers
        self.start_btn.config(state=tk.NORMAL if has_path and not is_following else tk.DISABLED)
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
        self.info_label.config(
            text=f"{prefix} {self.active_robot}: ({x:6.3f}, {y:6.3f})m | {yaw_deg:6.1f}°"
        )
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
            color = "#ff9900" if is_dummy else "#0066ff"
            outline = "#ffcc00" if is_dummy else "#00aaff"
            if is_following:
                outline = "#00ff88"
                width = 5 if is_active else 3
            elif has_path:
                outline = "#ffaa00"
                width = 4 if is_active else 2
            else:
                width = 4 if is_active else 2

            visual = self.canvas.create_oval(
                x - size,
                y - size,
                x + size,
                y + size,
                fill=color,
                outline=outline,
                width=width,
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
                fill="#fff",
                width=3 if is_active else 2,
                arrow=tk.LAST,
                tags="robot_arrow",
            )

            label_text = name if is_active else name[:6]
            self.canvas.create_text(
                x,
                y - size - 10,
                text=label_text,
                fill="#fff" if is_active else "#888",
                font=("Arial", 9 if is_active else 7, "bold"),
                tags="robot_label",
            )

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
        if event.widget != self.root:
            return
        window_width = event.width
        window_height = event.height
        left_panel_width = 280
        joystick_width = 300 if self.current_mode == self.MODE_RECORD else 0
        available_width = window_width - left_panel_width - joystick_width - 60
        available_height = window_height - 200
        if available_width <= 0 or available_height <= 0:
            return
        aspect_ratio = 16 / 9
        if available_width / available_height > aspect_ratio:
            new_height = max(400, available_height)
            new_width = int(new_height * aspect_ratio)
        else:
            new_width = max(800, available_width)
            new_height = int(new_width / aspect_ratio)
        if abs(new_width - self.canvas_width) > 50 or abs(new_height - self.canvas_height) > 50:
            self.canvas_width = new_width
            self.canvas_height = new_height
            self.canvas.config(width=self.canvas_width, height=self.canvas_height)
            self.canvas.delete("grid", "origin")
            self.grid_helper.width = self.canvas_width
            self.grid_helper.height = self.canvas_height
            self.grid_helper.draw_grid()
            if self.robot_visuals:
                self._draw_robots()

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
