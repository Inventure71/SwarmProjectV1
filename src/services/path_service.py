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
    
    def __init__(self, canvas, world_to_canvas_func, canvas_to_world_func):
        self.canvas = canvas
        self.world_to_canvas = world_to_canvas_func
        self.canvas_to_world = canvas_to_world_func
        
        self.robot_paths: Dict[str, Dict[str, Any]] = {}
        self.path_colors = ['#00ff88', '#00aaff', '#ff6600', '#ff00ff', '#ffff00', '#00ffff']
    
    def _get_robot_path(self, robot_name: str) -> Dict[str, Any]:
        """Get or create path data for a robot."""
        if robot_name not in self.robot_paths:
            idx = len(self.robot_paths) % len(self.path_colors)
            self.robot_paths[robot_name] = {
                'path_points': [],
                'recorded_positions': [],
                'color': self.path_colors[idx]
            }
        return self.robot_paths[robot_name]
    
    def add_waypoint(self, robot_name: str, x: int, y: int, mode: str = "click"):
        """Add a waypoint for a specific robot."""
        path_data = self._get_robot_path(robot_name)
        path_data['path_points'].append((x, y))
        
        color = path_data['color']
        tag = f'waypoint_{robot_name}'
        line_tag = f'path_line_{robot_name}'
        
        if mode == "draw":
            size = 3
            self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                   fill=color, outline=color, tags=tag)
        else:
            size = 6
            self.canvas.create_oval(x - size, y - size, x + size, y + size,
                                   fill=color, outline='#fff', width=2, tags=tag)
            self.canvas.create_text(x, y - 16, text=str(len(path_data['path_points'])),
                                   fill=color, font=('Arial', 10, 'bold'), tags=tag)
        
        if len(path_data['path_points']) > 1:
            prev_x, prev_y = path_data['path_points'][-2]
            self.canvas.create_line(prev_x, prev_y, x, y, fill=color, width=3, tags=line_tag)
        
        return len(path_data['path_points'])
    
    def set_recorded_path(self, robot_name: str, positions: List[Tuple[float, float]]):
        """Set path from recorded positions for a specific robot."""
        path_data = self._get_robot_path(robot_name)
        path_data['recorded_positions'] = positions
        path_data['path_points'] = []
        
        for x_m, y_m in positions:
            x, y = self.world_to_canvas(x_m, y_m)
            path_data['path_points'].append((x, y))
        
        self._redraw_path(robot_name)
    
    def _redraw_path(self, robot_name: str):
        """Redraw path for a specific robot."""
        if robot_name not in self.robot_paths:
            return
        
        path_data = self.robot_paths[robot_name]
        tag = f'waypoint_{robot_name}'
        line_tag = f'path_line_{robot_name}'
        
        self.canvas.delete(tag)
        self.canvas.delete(line_tag)
        
        color = path_data['color']
        for i, (x, y) in enumerate(path_data['path_points']):
            size = 3
            self.canvas.create_oval(
                x - size, y - size, x + size, y + size,
                fill=color, outline=color, tags=tag
            )
            
            if i > 0:
                prev_x, prev_y = path_data['path_points'][i-1]
                self.canvas.create_line(
                    prev_x, prev_y, x, y,
                    fill=color, width=3, tags=line_tag
                )
    
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
        path_points = self.robot_paths[robot_name]['path_points']
        waypoints = [self.canvas_to_world(x, y) for x, y in path_points]
        
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
        if robot_name not in self.robot_paths or len(self.robot_paths[robot_name]['path_points']) == 0:
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
                for x_m, y_m in waypoints_meters:
                    x, y = self.world_to_canvas(x_m, y_m)
                    path_data['path_points'].append((x, y))
                
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
            "num_waypoints": len(path_data['path_points']),
            "is_recorded": len(path_data['recorded_positions']) > 0,
            "waypoints_meters": self.get_waypoints_meters(robot_name, loop)
        }
    
    def has_path(self, robot_name: str) -> bool:
        """Check if robot has a path."""
        return robot_name in self.robot_paths and len(self.robot_paths[robot_name]['path_points']) > 0

