#!/usr/bin/env python3
"""
Dashboard Tab
Main control view with canvas and controls.
"""

import tkinter as tk
from ui.components import ModernButton, CanvasGrid, StatusLabel
from ui.tabbed_interface import CollapsibleSection
from ui.virtual_joystick import VirtualJoystick


class DashboardTab:
    """Dashboard tab with main controls and canvas."""
    
    def __init__(self, parent, state, canvas_handler, mode_handler, button_handler):
        self.state = state
        self.canvas_handler = canvas_handler
        self.mode_handler = mode_handler
        self.button_handler = button_handler
        
        self.frame = parent
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup dashboard UI."""
        # Configure grid weights for proper resizing
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Top status bar
        self._setup_status_bar()
        
        # Main content area
        content_area = tk.Frame(self.frame, bg="#0f0f0f")
        content_area.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        content_area.grid_rowconfigure(0, weight=1)
        content_area.grid_columnconfigure(1, weight=1)
        
        # Left sidebar with controls
        self._setup_sidebar(content_area)
        
        # Canvas area
        self._setup_canvas_area(content_area)
    
    def _setup_status_bar(self):
        """Setup status bar at the top."""
        status_bar = tk.Frame(self.frame, bg="#1e1e1e", height=60)
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
        
        self.robot_var = tk.StringVar()
        self.robot_dropdown = tk.OptionMenu(
            robot_selector_frame,
            self.robot_var,
            "",
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
    
    def _setup_sidebar(self, parent):
        """Setup left sidebar with controls."""
        sidebar = tk.Frame(parent, bg="#1e1e1e", width=360)
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
        self._create_quick_controls(sidebar_content)
        
        # Mode Selection Section
        self._create_mode_selection(sidebar_content)
        
        # Robot Config Section Placeholder (will be populated by app)
        self.robot_config_container = tk.Frame(sidebar_content, bg="#1e1e1e")
        self.robot_config_container.pack(fill=tk.X, padx=10, pady=8)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        sidebar_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        sidebar_canvas.bind_all("<Button-4>", lambda e: sidebar_canvas.yview_scroll(-1, "units"))
        sidebar_canvas.bind_all("<Button-5>", lambda e: sidebar_canvas.yview_scroll(1, "units"))
    
    def _create_quick_controls(self, parent):
        """Create quick control buttons."""
        quick_controls = CollapsibleSection(parent, "⚡ Quick Controls", bg="#1e1e1e")
        quick_controls.pack(fill=tk.X, padx=10, pady=8)
        
        self.start_btn = ModernButton(
            quick_controls.content,
            text="▶ START PATH",
            style="success",
            command=self.button_handler.start_path,
            state=tk.DISABLED,
        )
        self.start_btn.config(pady=12, font=("Segoe UI", 11, "bold"))
        self.start_btn.pack(fill=tk.X, padx=8, pady=4)
        
        self.stop_btn = ModernButton(
            quick_controls.content,
            text="⏸ STOP",
            style="warning",
            command=self.button_handler.stop_path,
            state=tk.DISABLED,
        )
        self.stop_btn.config(pady=12, font=("Segoe UI", 11, "bold"))
        self.stop_btn.pack(fill=tk.X, padx=8, pady=4)
        
        self.emergency_btn = ModernButton(
            quick_controls.content,
            text="🛑 EMERGENCY STOP",
            style="danger",
            command=self.button_handler.emergency_stop,
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
            command=self.button_handler.start_all_paths,
        )
        self.start_all_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.stop_all_btn = ModernButton(
            btn_frame,
            text="⏸ ALL",
            style="warning",
            command=self.button_handler.stop_all_paths,
        )
        self.stop_all_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
    
    def _create_mode_selection(self, parent):
        """Create mode selection buttons."""
        mode_section = CollapsibleSection(parent, "🎯 Path Creation Mode", bg="#1e1e1e")
        mode_section.pack(fill=tk.X, padx=10, pady=8)
        
        self.mode_buttons = {}
        modes = [
            (self.state.MODE_CLICK, "📍 Click Mode"),
            (self.state.MODE_DRAW, "✏️ Draw Mode"),
            (self.state.MODE_RECORD, "🎮 Record Mode"),
        ]
        for mode_id, label in modes:
            btn = ModernButton(
                mode_section.content,
                text=label,
                style="secondary",
                command=lambda value=mode_id: self.mode_handler.switch_mode(value),
            )
            btn.pack(fill=tk.X, padx=8, pady=4)
            self.mode_buttons[mode_id] = btn
    
    def _setup_canvas_area(self, parent):
        """Setup canvas area."""
        canvas_container = tk.Frame(parent, bg="#0f0f0f")
        canvas_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        canvas_container.grid_rowconfigure(1, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(1, weight=0)
        
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
        
        # Canvas wrapper
        canvas_wrapper = tk.Frame(canvas_container, bg="#1e1e1e", bd=0, relief=tk.FLAT, highlightbackground="#333333", highlightthickness=1)
        canvas_wrapper.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        canvas_wrapper.grid_rowconfigure(0, weight=1)
        canvas_wrapper.grid_columnconfigure(0, weight=1)
        
        # Canvas
        self.canvas = tk.Canvas(
            canvas_wrapper,
            width=self.state.canvas_width,
            height=self.state.canvas_height,
            bg="#0a0a0a",
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        
        self.grid_helper = CanvasGrid(self.canvas, self.state.scale, self.state.canvas_width, self.state.canvas_height)
        self.grid_helper.draw_grid()
        
        # Bind canvas events
        self.canvas.bind("<Button-1>", self.canvas_handler.on_click)
        self.canvas.bind("<B1-Motion>", self.canvas_handler.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.canvas_handler.on_release)
        
        # Joystick container (hidden by default)
        self._setup_joystick_container(canvas_container)
    
    def _setup_joystick_container(self, parent):
        """Setup joystick container."""
        self.joystick_container = tk.Frame(parent, bg="#0f0f0f", width=320)
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
            command=None,  # Will be set by app
        )
        self.record_btn.config(pady=12, font=("Segoe UI", 11, "bold"))
        self.record_btn.pack(fill=tk.X, padx=15, pady=(0, 15))
    
    def update_mode_buttons(self):
        """Update mode button styles."""
        for mode_id, button in self.mode_buttons.items():
            if mode_id == self.state.current_mode:
                button.config(bg="#00d4aa", fg="#000000", activeforeground="#000000", relief=tk.FLAT)
            else:
                button.config(bg="#424242", fg="#000000", activeforeground="#000000", relief=tk.FLAT)

