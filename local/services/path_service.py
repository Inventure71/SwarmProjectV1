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
    """Service for managing per-robot paths."""
    
    def __init__(self, canvas, world_to_canvas_func, canvas_to_world_func, color_provider=None):
        self.canvas = canvas
        self.world_to_canvas = world_to_canvas_func
        self.canvas_to_world = canvas_to_world_func
        
        self.robot_paths: Dict[str, Dict[str, Any]] = {}
        self.path_colors = ['#00ff88', '#00aaff', '#ff6600', '#ff00ff', '#ffff00', '#00ffff']
        self._color_provider = color_provider
    
    def _get_robot_path(self, robot_name: str) -> Dict[str, Any]:
        """Get or create path data for a robot."""
        if robot_name not in self.robot_paths:
            idx = len(self.robot_paths) % len(self.path_colors)
            color = None
            if callable(self._color_provider):
                try:
                    color = self._color_provider(robot_name)
                except Exception:
                    color = None
            if not color:
                color = self.path_colors[idx]
            self.robot_paths[robot_name] = {
                'path_points_world': [],  # Store in world coordinates (meters)
                'path_points': [],  # Legacy - kept for compatibility
                'recorded_positions': [],
                'color': color
            }
        return self.robot_paths[robot_name]

    def set_path_color(self, robot_name: str, color: str, redraw: bool = True) -> None:
        path_data = self._get_robot_path(robot_name)
        path_data['color'] = color
        if redraw:
            self._redraw_path(robot_name)
    
    def add_waypoint(self, robot_name: str, x: int, y: int, mode: str = "click"):
        """Add a waypoint for a specific robot. x, y are canvas coordinates."""
        path_data = self._get_robot_path(robot_name)
        
        # Convert canvas coordinates to world coordinates for storage
        x_world, y_world = self.canvas_to_world(x, y)
        path_data['path_points_world'].append((x_world, y_world))
        path_data['path_points'].append((x, y))  # Keep for legacy compatibility
        
        # Redraw entire path to reflect current zoom/pan
        self._redraw_path(robot_name)
        
        return len(path_data['path_points_world'])
    
    def set_recorded_path(self, robot_name: str, positions: List[Tuple[float, float]]):
        """Set path from recorded positions for a specific robot. Positions are in world coordinates (meters)."""
        path_data = self._get_robot_path(robot_name)
        path_data['recorded_positions'] = positions
        path_data['path_points_world'] = positions.copy()  # Store world coordinates
        path_data['path_points'] = []  # Clear legacy
        
        self._redraw_path(robot_name)
    
    def _redraw_path(self, robot_name: str):
        """Redraw path for a specific robot, converting world coordinates to canvas coordinates."""
        if robot_name not in self.robot_paths:
            return
        
        path_data = self.robot_paths[robot_name]
        tag = f'waypoint_{robot_name}'
        line_tag = f'path_line_{robot_name}'
        
        self.canvas.delete(tag)
        self.canvas.delete(line_tag)
        
        # Use world coordinates and convert to canvas coordinates based on current zoom/pan
        world_points = path_data.get('path_points_world', [])
        if not world_points:
            return
        
        color = path_data['color']
        prev_canvas_x, prev_canvas_y = None, None
        
        for i, (x_world, y_world) in enumerate(world_points):
            # Convert world coordinates to canvas coordinates
            canvas_x, canvas_y = self.world_to_canvas(x_world, y_world)
            
            size = 3
            self.canvas.create_oval(
                canvas_x - size, canvas_y - size, canvas_x + size, canvas_y + size,
                fill=color, outline=color, tags=tag
            )
            
            # Draw line to previous point
            if prev_canvas_x is not None:
                self.canvas.create_line(
                    prev_canvas_x, prev_canvas_y, canvas_x, canvas_y,
                    fill=color, width=3, tags=line_tag
                )
            
            prev_canvas_x, prev_canvas_y = canvas_x, canvas_y
    
    def clear_path(self, robot_name: str):
        """Clear waypoints and path for a specific robot."""
        if robot_name in self.robot_paths:
            del self.robot_paths[robot_name]
        self.canvas.delete(f'waypoint_{robot_name}')
        self.canvas.delete(f'path_line_{robot_name}')
        self.canvas.delete(f'recording_trace_{robot_name}')
    
    def clear_all_paths(self):
        """Clear all robot paths."""
        for robot_name in list(self.robot_paths.keys()):
            self.clear_path(robot_name)
    
    def get_waypoints_meters(self, robot_name: str, loop: bool = False) -> List[Tuple[float, float]]:
        """Get waypoints in world coordinates for a specific robot."""
        if robot_name not in self.robot_paths:
            return []
        # Use world coordinates directly
        waypoints = self.robot_paths[robot_name].get('path_points_world', []).copy()
        
        if loop and len(waypoints) > 2:
            first = waypoints[0]
            last = waypoints[-1]
            dx = first[0] - last[0]
            dy = first[1] - last[1]
            dist = (dx**2 + dy**2)**0.5
            
            if dist > 0.5:
                num_bridge = max(3, int(dist / 0.3))
                for i in range(1, num_bridge):
                    t = i / num_bridge
                    t_smooth = t * t * (3 - 2 * t)
                    bx = last[0] + dx * t_smooth
                    by = last[1] + dy * t_smooth
                    waypoints.append((bx, by))
            
            waypoints.append(first)
        
        return waypoints
    
    def save_path(self, robot_name: str) -> bool:
        """Save path for a specific robot."""
        if robot_name not in self.robot_paths or len(self.robot_paths[robot_name].get('path_points_world', [])) == 0:
            messagebox.showinfo("Save Path", f"No path to save for {robot_name}!")
            return False
        
        waypoints_meters = self.get_waypoints_meters(robot_name)
        
        filename = filedialog.asksaveasfilename(
            title=f"Save Path - {robot_name}",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"path_{robot_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        if filename:
            try:
                path_data = self.robot_paths[robot_name]
                data = {
                    "robot": robot_name,
                    "timestamp": datetime.now().isoformat(),
                    "waypoints": waypoints_meters,
                    "num_points": len(waypoints_meters),
                    "is_recorded": len(path_data['recorded_positions']) > 0
                }
                
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
                
                messagebox.showinfo("Save Path", f"Path saved for {robot_name}!\n{len(waypoints_meters)} waypoints")
                return True
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save path:\n{e}")
                return False
        
        return False
    
    def load_path(self, robot_name: str) -> bool:
        """Load path for a specific robot."""
        filename = filedialog.askopenfilename(
            title=f"Load Path - {robot_name}",
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
                
                self.clear_path(robot_name)
                
                path_data = self._get_robot_path(robot_name)
                # Store in world coordinates
                path_data['path_points_world'] = waypoints_meters.copy()
                
                self._redraw_path(robot_name)
                
                messagebox.showinfo("Load Path", f"Path loaded for {robot_name}!\n{len(waypoints_meters)} waypoints")
                return True
                
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load path:\n{e}")
                return False
        
        return False
    
    def get_path_info(self, robot_name: str, loop: bool = False) -> Dict[str, Any]:
        """Get path information for a specific robot."""
        if robot_name not in self.robot_paths:
            return {
                "num_waypoints": 0,
                "is_recorded": False,
                "waypoints_meters": []
            }
        
        path_data = self.robot_paths[robot_name]
        return {
            "num_waypoints": len(path_data.get('path_points_world', [])),
            "is_recorded": len(path_data['recorded_positions']) > 0,
            "waypoints_meters": self.get_waypoints_meters(robot_name, loop)
        }
    
    def has_path(self, robot_name: str) -> bool:
        """Check if robot has a path."""
        return robot_name in self.robot_paths and len(self.robot_paths[robot_name].get('path_points_world', [])) > 0

