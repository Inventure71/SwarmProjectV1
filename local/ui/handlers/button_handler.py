#!/usr/bin/env python3
"""
Button Event Handler
Handles button click events for robot control.
"""

from tkinter import messagebox


class ButtonHandler:
    """Handles button events for robot control."""
    
    def __init__(self, state, path_service, command_sender, racing_configs, update_ui_callback):
        self.state = state
        self.path_service = path_service
        self.command_sender = command_sender
        self.racing_configs = racing_configs
        self.update_ui = update_ui_callback
    
    def start_path(self):
        """Start path following for active robot."""
        robot_name = self.state.active_robot
        cfg = self.racing_configs[robot_name]
        info = self.path_service.get_path_info(robot_name, cfg.loop_path)
        
        if info["num_waypoints"] == 0:
            return
        
        waypoints = info["waypoints_meters"]
        self.command_sender.push_path_to_backend(robot_name, waypoints)
        self.command_sender.send_racing_config(robot_name, cfg)
        self.command_sender.start_path(robot_name)
        
        self.update_ui("start", robot_name)
    
    def stop_path(self):
        """Stop path following for active robot."""
        robot_name = self.state.active_robot
        self.command_sender.stop_path(robot_name)
        self.update_ui("stop", robot_name)
    
    def start_all_paths(self):
        """Start path following for all robots with paths."""
        started = 0
        for name in self.state.robots.keys():
            cfg = self.racing_configs[name]
            info = self.path_service.get_path_info(name, cfg.loop_path)
            
            if info["num_waypoints"] == 0:
                continue
            
            waypoints = info["waypoints_meters"]
            self.command_sender.push_path_to_backend(name, waypoints)
            self.command_sender.send_racing_config(name, cfg)
            started += 1
        
        if started:
            self.command_sender.start_all_paths()
            self.update_ui("start_all", started)
    
    def stop_all_paths(self):
        """Stop all robots."""
        self.command_sender.stop_all()
        self.update_ui("stop_all")
    
    def emergency_stop(self):
        """Emergency stop all robots."""
        self.command_sender.emergency_stop()
        self.update_ui("emergency")
    
    def clear_path(self):
        """Clear path for active robot."""
        robot_name = self.state.active_robot
        self.command_sender.clear_path(robot_name)
        self.path_service.clear_path(robot_name)
        self.state.is_drawing = False
        self.state.last_draw_point = None
        self.update_ui("clear")
    
    def save_path(self):
        """Save path for active robot."""
        self.path_service.save_path(self.state.active_robot)
        self.update_ui("save")
    
    def load_path(self):
        """Load path for active robot."""
        if self.path_service.load_path(self.state.active_robot):
            info = self.path_service.get_path_info(self.state.active_robot)
            self.update_ui("load", info)

