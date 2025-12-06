#!/usr/bin/env python3
"""
Backend Message Handler
Processes messages received from the backend.
"""

from typing import Dict, Callable
from tkinter import messagebox


class BackendMessageHandler:
    """Handles messages received from the backend server."""
    
    def __init__(self, state):
        self.state = state
    
    def handle_message(self, message: Dict) -> None:
        """Process a message from the backend."""
        msg_type = message.get("type")
        data = message.get("data", {})
        
        if msg_type == "robot_states" and isinstance(data, dict):
            self.state.update_robot_states(data)
        elif msg_type == "path_following_state" and isinstance(data, dict):
            self.state.update_follower_states(data)
        elif msg_type == "connection_status" and isinstance(data, dict):
            self.state.update_connection_status(data)
        elif msg_type == "error":
            messagebox.showwarning("Backend", str(data.get("message", data)))

