#!/usr/bin/env python3
"""
Robot List Widget
Widget for displaying and managing robot list.
"""

import tkinter as tk
from ui.components import ModernButton


class RobotListWidget:
    """Widget for displaying list of robots."""
    
    def __init__(self, parent, state, select_callback):
        self.parent = parent
        self.state = state
        self.select_callback = select_callback
        self.frame = tk.Frame(parent, bg="#1e1e1e")
    
    def update_display(self):
        """Update the robot list display."""
        # Clear existing widgets
        for widget in self.frame.winfo_children():
            widget.destroy()
        
        # Header
        header = tk.Frame(self.frame, bg="#2d2d2d")
        header.pack(fill=tk.X, pady=2)
        tk.Label(header, text="Name", bg="#2d2d2d", fg="#00d4aa", font=("Segoe UI", 10, "bold"), width=12).pack(side=tk.LEFT, padx=5)
        tk.Label(header, text="Type", bg="#2d2d2d", fg="#00d4aa", font=("Segoe UI", 10, "bold"), width=8).pack(side=tk.LEFT, padx=5)
        tk.Label(header, text="Battery", bg="#2d2d2d", fg="#00d4aa", font=("Segoe UI", 10, "bold"), width=10).pack(side=tk.LEFT, padx=5)
        tk.Label(header, text="Status", bg="#2d2d2d", fg="#00d4aa", font=("Segoe UI", 10, "bold"), width=10).pack(side=tk.LEFT, padx=5)
        
        # Robot rows
        follower_states = self.state.get_follower_states()
        
        for name, proxy in self.state.robots.items():
            row = tk.Frame(self.frame, bg="#1e1e1e")
            row.pack(fill=tk.X, pady=2)
            
            is_active = name == self.state.active_robot
            fg_color = "#ffffff" if is_active else "#e0e0e0"
            
            tk.Label(row, text=name, bg="#1e1e1e", fg=fg_color, font=("Segoe UI", 10), width=12).pack(side=tk.LEFT, padx=5)
            tk.Label(row, text=proxy.robot_type, bg="#1e1e1e", fg=fg_color, font=("Segoe UI", 10), width=8).pack(side=tk.LEFT, padx=5)
            
            # Battery
            battery = self.state.get_robot_battery(name)
            if battery and battery.get('percentage') is not None:
                batt_pct = battery['percentage']
                if batt_pct >= 50:
                    batt_color = "#00ff88"
                elif batt_pct >= 20:
                    batt_color = "#ffaa00"
                else:
                    batt_color = "#ff4444"
                charging = "⚡" if battery.get('charging') else ""
                batt_text = f"{batt_pct:.0f}%{charging}"
            else:
                batt_text = "N/A"
                batt_color = "#666666"
            tk.Label(row, text=batt_text, bg="#1e1e1e", fg=batt_color, font=("Segoe UI", 10), width=10).pack(side=tk.LEFT, padx=5)
            
            # Status
            is_following = name in follower_states
            status_text = "Following" if is_following else "Idle"
            status_color = "#00d4aa" if is_following else "#9e9e9e"
            tk.Label(row, text=status_text, bg="#1e1e1e", fg=status_color, font=("Segoe UI", 10), width=10).pack(side=tk.LEFT, padx=5)
            
            # Select button
            if not is_active:
                select_btn = ModernButton(row, text="Select", style="secondary", command=lambda n=name: self.select_callback(n))
                select_btn.config(font=("Segoe UI", 8))
                select_btn.pack(side=tk.RIGHT, padx=5)
    
    def pack(self, **kwargs):
        """Pack the frame."""
        self.frame.pack(**kwargs)

