#!/usr/bin/env python3
"""
Robots Tab
Robot management interface.
"""

import tkinter as tk
from ui.components import ModernButton
from ui.tabbed_interface import CollapsibleSection
from ui.widgets import RobotListWidget


class RobotsTab:
    """Robots tab for robot management."""
    
    def __init__(self, parent, state, robot_handler):
        self.state = state
        self.robot_handler = robot_handler
        self.frame = parent
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup robots tab UI."""
        # Use grid layout
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable content
        robots_canvas = tk.Canvas(self.frame, bg="#0f0f0f", highlightthickness=0)
        robots_scrollbar = tk.Scrollbar(self.frame, orient=tk.VERTICAL, command=robots_canvas.yview)
        robots_content = tk.Frame(robots_canvas, bg="#0f0f0f")
        
        robots_content.bind("<Configure>", lambda e: robots_canvas.configure(scrollregion=robots_canvas.bbox("all")))
        robots_canvas.create_window((0, 0), window=robots_content, anchor="nw")
        robots_canvas.configure(yscrollcommand=robots_scrollbar.set)
        
        robots_canvas.grid(row=0, column=0, sticky="nsew")
        robots_scrollbar.grid(row=0, column=1, sticky="ns")
        
        robots_content.grid_columnconfigure(0, weight=1)
        
        # Robot List Section
        robot_list_section = CollapsibleSection(robots_content, "📋 Robot List", bg="#1e1e1e", expanded=True)
        robot_list_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.robot_list_widget = RobotListWidget(
            robot_list_section.content,
            self.state,
            self.robot_handler.select_robot
        )
        self.robot_list_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add Robot Section
        self._create_add_robot_section(robots_content)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            robots_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        robots_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def _create_add_robot_section(self, parent):
        """Create add robot section."""
        add_robot_section = CollapsibleSection(parent, "➕ Add New Robot", bg="#1e1e1e", expanded=True)
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
        add_button = ModernButton(add_form, text="➕ Add Robot", style="primary", command=None)  # Will be set by app
        add_button.grid(row=3, column=0, columnspan=2, pady=15, padx=10, sticky="ew")
        self.add_button = add_button
        
        add_form.columnconfigure(1, weight=1)
    
    def update_robot_list(self):
        """Update the robot list display."""
        self.robot_list_widget.update_display()

