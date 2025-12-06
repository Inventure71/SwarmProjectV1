#!/usr/bin/env python3
"""
Robot Renderer
Handles visualization of robots on the canvas.
"""

import math
import tkinter as tk
from typing import Dict, Set, Tuple


class RobotRenderer:
    """Renders robots on the canvas with visual indicators."""
    
    def __init__(self, canvas: tk.Canvas, coordinate_converter):
        self.canvas = canvas
        self.coordinates = coordinate_converter
    
    def draw_robots(
        self,
        robots: Dict[str, object],
        positions: Dict[str, Tuple[float, float, float]],
        followers: Set[str],
        robot_colors: Dict[str, str],
        active_robot: str,
        has_path_func
    ) -> Dict[str, int]:
        """
        Draw all robots on the canvas.
        
        Args:
            robots: Dictionary of robot proxy objects
            positions: Robot positions (x, y, yaw)
            followers: Set of robots currently following paths
            robot_colors: Color for each robot
            active_robot: Name of the active robot
            has_path_func: Function to check if robot has a path
            
        Returns:
            Dictionary mapping robot names to canvas visual IDs
        """
        # Clear existing visuals
        self.canvas.delete("robot_arrow")
        self.canvas.delete("robot_label")
        
        robot_visuals = {}
        
        for name, proxy in robots.items():
            x_m, y_m, yaw = positions.get(name, (0.0, 0.0, 0.0))
            x, y = self.coordinates.world_to_canvas(x_m, y_m)
            
            is_active = name == active_robot
            is_dummy = proxy.robot_type == "dummy"
            has_path = has_path_func(name)
            is_following = name in followers
            
            visual = self._draw_single_robot(
                x, y, yaw, name,
                is_active, has_path, is_following,
                robot_colors.get(name, "#00aaff")
            )
            robot_visuals[name] = visual
        
        return robot_visuals
    
    def _draw_single_robot(
        self,
        x: float, y: float, yaw: float,
        name: str,
        is_active: bool,
        has_path: bool,
        is_following: bool,
        base_color: str
    ) -> int:
        """Draw a single robot on the canvas."""
        size = 22 if is_active else 16
        
        # Calculate colors
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
            try:
                outline_r = max(0, int(r * 0.5))
                outline_g = max(0, int(g * 0.5))
                outline_b = max(0, int(b * 0.5))
                outline_color = f"#{outline_r:02x}{outline_g:02x}{outline_b:02x}"
            except Exception:
                outline_color = "#333333"
        
        # Determine outline width based on state
        if is_following:
            outline_width = 5 if is_active else 3
        elif has_path:
            outline_width = 4 if is_active else 2
        else:
            outline_width = 3 if is_active else 2
        
        # Draw robot circle
        visual = self.canvas.create_oval(
            x - size,
            y - size,
            x + size,
            y + size,
            fill=fill_color,
            outline=outline_color,
            width=outline_width,
        )
        
        # Draw direction arrow
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
        
        # Draw label
        label_text = name if is_active else name[:6]
        self.canvas.create_text(
            x,
            y - size - 10,
            text=label_text,
            fill=base_color if is_active else "#888",
            font=("Arial", 9 if is_active else 7, "bold"),
            tags="robot_label",
        )
        
        return visual

