#!/usr/bin/env python3
"""
Backend Message Handler
Processes messages received from the supervisor bridge.
"""

from typing import Callable, Dict, Optional


class BackendMessageHandler:
    """Handles messages received from the supervisor bridge."""
    
    def __init__(self, state, on_error: Optional[Callable[[str], None]] = None):
        self.state = state
        self.on_error = on_error
    
    def handle_message(self, message: Dict) -> None:
        """Process a message from the supervisor bridge."""
        msg_type = message.get("type")
        data = message.get("data", {})
        
        if msg_type == "robot_states" and isinstance(data, dict):
            self.state.update_robot_states(data)
        elif msg_type == "path_following_state" and isinstance(data, dict):
            self.state.update_follower_states(data)
        elif msg_type == "connection_status" and isinstance(data, dict):
            self.state.update_connection_status(data)
        elif msg_type == "error":
            error_text = str(data.get("message", data))
            if self.on_error:
                self.on_error(error_text)
