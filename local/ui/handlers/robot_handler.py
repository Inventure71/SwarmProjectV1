#!/usr/bin/env python3
"""
Robot Handler
Handles robot selection and management events.
"""

from tkinter import messagebox


class RobotHandler:
    """Handles robot management operations."""
    
    def __init__(self, state, config_loader, udp_client, command_sender, racing_config_class, proxy_class, update_ui_callback):
        self.state = state
        self.config_loader = config_loader
        self.udp_client = udp_client
        self.command_sender = command_sender
        self.racing_config_class = racing_config_class
        self.proxy_class = proxy_class
        self.update_ui = update_ui_callback
    
    def select_robot(self, robot_name: str):
        """Select a robot as the active robot."""
        if robot_name not in self.state.robots:
            return
        
        self.state.active_robot = robot_name
        self.update_ui("select", robot_name)
    
    def add_robot(self, name: str, umh_id: str, robot_type: str, app_instance):
        """Add a new robot to the system."""
        messagebox.showwarning(
            "Add Robot",
            "Runtime add/remove is disabled in the ROS 2 architecture.\n"
            "Update config/fleet.json and relaunch the supervisor/UI instead."
        )
        return False

    def _legacy_add_robot(self, name: str, umh_id: str, robot_type: str, app_instance):
        """Legacy add robot flow retained for reference."""
        if not name:
            messagebox.showwarning("Add Robot", "Please provide a robot name.")
            return False
        
        if name in self.state.robots:
            messagebox.showwarning("Add Robot", f"Robot '{name}' already exists.")
            return False
        
        if robot_type == "real" and not umh_id:
            messagebox.showwarning("Add Robot", "Please provide UMH ID for real robots.")
            return False
        
        robot_config = {
            "name": name,
            "type": robot_type,
            "umh_id": umh_id if robot_type == "real" else None,
            "cmd_vel_topic": f"/{name}/cmd_vel" if robot_type == "real" else None,
        }
        
        # Legacy path kept only for reference.
        self.command_sender.add_robot(robot_config)
        ack = self.udp_client.wait_for_ack("add_robot", timeout=1.0)
        if not ack:
            messagebox.showwarning("Add Robot", "No confirmation from supervisor. Robot may not have been added.")
        
        # Update config
        self.config_loader.upsert_robot(name, robot_config)
        updated_cfg = self.config_loader.get_robot_by_name(name) or robot_config
        
        # Add to state
        self.state.robot_configs[name] = updated_cfg
        self.state.robots[name] = self.proxy_class(app_instance, name, robot_type)
        self.state.racing_configs[name] = self.racing_config_class(name)
        self.state.robot_colors[name] = updated_cfg.get("color", "#00aaff")
        self.state.set_robot_position(name, 0.0, 0.0, 0.0)
        
        self.update_ui("add", name)
        
        messagebox.showinfo("Add Robot", f"Robot '{name}' added. Use set path to start tracking.")
        return True
