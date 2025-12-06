#!/usr/bin/env python3
"""
Status Bar Widget
Widget for displaying connection and system status.
"""

import tkinter as tk
from ui.components import StatusLabel


class StatusBar:
    """Status bar widget for displaying connection status."""
    
    def __init__(self, parent, robot_selector_callback):
        self.frame = tk.Frame(parent, bg="#1e1e1e", height=60)
        self.frame.grid_propagate(False)
        self.frame.grid_columnconfigure(1, weight=1)
        
        # Status indicator on left
        status_left = tk.Frame(self.frame, bg="#1e1e1e")
        status_left.grid(row=0, column=0, sticky="w", padx=20, pady=10)
        self.status_label = StatusLabel(status_left, text="⚪ Not Connected", fg="#9e9e9e")
        self.status_label.pack(side=tk.LEFT)
        
        # Quick robot selector on right
        robot_selector_frame = tk.Frame(self.frame, bg="#1e1e1e")
        robot_selector_frame.grid(row=0, column=1, sticky="e", padx=20, pady=10)
        
        tk.Label(robot_selector_frame, text="Active Robot:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=5)
        
        self.robot_var = tk.StringVar()
        self.robot_dropdown = tk.OptionMenu(
            robot_selector_frame,
            self.robot_var,
            "",
            command=robot_selector_callback,
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
    
    def update_status(self, text: str, color: str):
        """Update status text and color."""
        self.status_label.config(text=text, fg=color)
    
    def update_robot_list(self, robots: list, active_robot: str, callback):
        """Update robot dropdown list."""
        self.robot_var.set(active_robot)
        menu = self.robot_dropdown["menu"]
        menu.delete(0, "end")
        for name in robots:
            menu.add_command(label=name, command=lambda value=name: callback(value))
    
    def grid(self, **kwargs):
        """Grid the frame."""
        self.frame.grid(**kwargs)

