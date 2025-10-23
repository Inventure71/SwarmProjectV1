#!/usr/bin/env python3
"""
Path Management Service
Handles saving, loading, and managing robot paths.
"""

import json
from datetime import datetime
from typing import List, Tuple, Dict, Any
from tkinter import filedialog, messagebox


class PathService:
    """Service for managing robot paths."""
    
    def __init__(self, canvas, world_to_canvas_func, canvas_to_world_func):
        self.canvas = canvas
        self.world_to_canvas = world_to_canvas_func
        self.canvas_to_world = canvas_to_world_func
        
        # Path data
        self.path_points: List[Tuple[int, int]] = []  # Canvas coordinates
        self.recorded_positions: List[Tuple[float, float]] = []  # World coordinates
    
    def add_waypoint(self, x: int, y: int, mode: str = "click"):
        """Add a waypoint at canvas coordinates."""
        self.path_points.append((x, y))
        
        # Draw waypoint marker
        if mode == "draw":
            size = 3
            color = '#00aaff'
            self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                   fill=color, outline=color, tags='waypoint')
        else:  # click mode
            size = 6
            color = '#00ff88'
            self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                   fill=color, outline='#fff', width=2, tags='waypoint')
            self.canvas.create_text(x, y - 16, text=str(len(self.path_points)),
                                   fill=color, font=('Arial', 10, 'bold'), tags='waypoint')
        
        # Draw line to previous point
        if len(self.path_points) > 1:
            prev_x, prev_y = self.path_points[-2]
            self.canvas.create_line(prev_x, prev_y, x, y, fill=color, width=3, tags='path_line')
        
        return len(self.path_points)
    
    def set_recorded_path(self, positions: List[Tuple[float, float]]):
        """Set path from recorded positions."""
        self.recorded_positions = positions
        self.path_points = []
        
        # Convert to canvas coordinates
        for x_m, y_m in positions:
            x, y = self.world_to_canvas(x_m, y_m)
            self.path_points.append((x, y))
        
        # Redraw path
        self._redraw_path()
    
    def _redraw_path(self):
        """Redraw the current path on canvas."""
        # Clear old path
        self.canvas.delete('waypoint')
        self.canvas.delete('path_line')
        
        # Draw path
        for i, (x, y) in enumerate(self.path_points):
            # Draw small waypoint markers
            size = 3
            color = '#ff6600' if self.recorded_positions else '#00ff88'
            self.canvas.create_oval(
                x - size, y - size, x + size, y + size,
                fill=color, outline=color, tags='waypoint'
            )
            
            # Draw line to previous point
            if i > 0:
                prev_x, prev_y = self.path_points[i-1]
                self.canvas.create_line(
                    prev_x, prev_y, x, y,
                    fill=color, width=3, tags='path_line'
                )
    
    def clear_path(self):
        """Clear all waypoints and path."""
        self.path_points = []
        self.recorded_positions = []
        self.canvas.delete('waypoint')
        self.canvas.delete('path_line')
        self.canvas.delete('recording_trace')
    
    def get_waypoints_meters(self) -> List[Tuple[float, float]]:
        """Get waypoints in world coordinates (meters)."""
        return [self.canvas_to_world(x, y) for x, y in self.path_points]
    
    def save_path(self, robot_name: str) -> bool:
        """Save current path to file."""
        if len(self.path_points) == 0:
            messagebox.showinfo("Save Path", "No path to save!")
            return False
        
        # Convert to world coordinates
        waypoints_meters = self.get_waypoints_meters()
        
        # Ask for filename
        filename = filedialog.asksaveasfilename(
            title="Save Path",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"path_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        if filename:
            try:
                data = {
                    "robot": robot_name,
                    "timestamp": datetime.now().isoformat(),
                    "waypoints": waypoints_meters,
                    "num_points": len(waypoints_meters),
                    "is_recorded": len(self.recorded_positions) > 0
                }
                
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
                
                messagebox.showinfo("Save Path", f"Path saved successfully!\n{len(waypoints_meters)} waypoints")
                return True
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save path:\n{e}")
                return False
        
        return False
    
    def load_path(self) -> bool:
        """Load path from file."""
        filename = filedialog.askopenfilename(
            title="Load Path",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                waypoints_meters = data.get("waypoints", [])
                
                if len(waypoints_meters) == 0:
                    messagebox.showwarning("Load Path", "No waypoints found in file!")
                    return False
                
                # Clear existing path
                self.clear_path()
                
                # Convert to canvas coordinates and add
                for x_m, y_m in waypoints_meters:
                    x, y = self.world_to_canvas(x_m, y_m)
                    self.path_points.append((x, y))
                
                # Redraw path
                self._redraw_path()
                
                messagebox.showinfo("Load Path", f"Path loaded successfully!\n{len(waypoints_meters)} waypoints")
                return True
                
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load path:\n{e}")
                return False
        
        return False
    
    def get_path_info(self) -> Dict[str, Any]:
        """Get information about the current path."""
        return {
            "num_waypoints": len(self.path_points),
            "is_recorded": len(self.recorded_positions) > 0,
            "waypoints_meters": self.get_waypoints_meters()
        }

