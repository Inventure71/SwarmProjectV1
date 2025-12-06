#!/usr/bin/env python3
"""
Robot Configuration Panel
Widget for configuring robot parameters (offset, speed, loop).
"""

import tkinter as tk
from ui.components import ModernScale, ModernCheckbutton


class RobotConfigPanel:
    """Panel for robot configuration controls."""
    
    def __init__(self, parent, racing_config, on_change_callback):
        self.racing_config = racing_config
        self.on_change = on_change_callback
        self.frame = tk.Frame(parent, bg="#1e1e1e")
        
        # Offset
        offset_frame = tk.Frame(self.frame, bg="#1e1e1e")
        offset_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(offset_frame, text="Lateral Offset:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10)).pack(anchor=tk.W)
        offset_control = tk.Frame(offset_frame, bg="#1e1e1e")
        offset_control.pack(fill=tk.X, pady=3)
        
        self.offset_var = tk.DoubleVar(value=racing_config.lateral_offset)
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
            text=f"{racing_config.lateral_offset:.2f}m",
            bg="#1e1e1e",
            fg="#00d4aa",
            font=("Segoe UI", 10, "bold"),
            width=6,
        )
        self.offset_label.pack(side=tk.LEFT, padx=8)
        
        # Speed
        speed_frame = tk.Frame(self.frame, bg="#1e1e1e")
        speed_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(speed_frame, text="Speed Multiplier:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10)).pack(anchor=tk.W)
        speed_control = tk.Frame(speed_frame, bg="#1e1e1e")
        speed_control.pack(fill=tk.X, pady=3)
        
        self.speed_var = tk.DoubleVar(value=racing_config.speed_multiplier)
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
            text=f"{racing_config.speed_multiplier:.1f}x",
            bg="#1e1e1e",
            fg="#00d4aa",
            font=("Segoe UI", 10, "bold"),
            width=6,
        )
        self.speed_label.pack(side=tk.LEFT, padx=8)
        
        # Loop checkbox
        self.loop_var = tk.BooleanVar(value=racing_config.loop_path)
        loop_check = ModernCheckbutton(
            self.frame,
            text="Loop Circuit",
            variable=self.loop_var,
            command=self._on_loop_change,
        )
        loop_check.pack(anchor=tk.W, padx=8, pady=4)
    
    def _on_offset_change(self, value):
        """Handle offset change."""
        offset = float(value)
        self.racing_config.set_offset(offset)
        self.offset_label.config(text=f"{offset:.2f}m")
        self.on_change("offset", offset)
    
    def _on_speed_change(self, value):
        """Handle speed change."""
        speed = float(value)
        self.racing_config.set_speed_multiplier(speed)
        self.speed_label.config(text=f"{speed:.1f}x")
        self.on_change("speed", speed)
    
    def _on_loop_change(self):
        """Handle loop change."""
        loop = self.loop_var.get()
        self.racing_config.set_loop(loop)
        self.on_change("loop", loop)
    
    def update_config(self, racing_config):
        """Update the panel with new racing config."""
        self.racing_config = racing_config
        self.offset_var.set(racing_config.lateral_offset)
        self.speed_var.set(racing_config.speed_multiplier)
        self.loop_var.set(racing_config.loop_path)
        self.offset_label.config(text=f"{racing_config.lateral_offset:.2f}m")
        self.speed_label.config(text=f"{racing_config.speed_multiplier:.1f}x")
    
    def pack(self, **kwargs):
        """Pack the frame."""
        self.frame.pack(**kwargs)

