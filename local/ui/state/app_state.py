#!/usr/bin/env python3
"""
Application State Management
Centralized state for the robot controller application.
"""

import threading
from typing import Dict, Tuple, Optional


class AppState:
    """Centralized application state with thread-safe access."""
    
    # Mode constants
    MODE_CLICK = "click"
    MODE_DRAW = "draw"
    MODE_RECORD = "record"
    
    def __init__(self):
        self._lock = threading.Lock()
        
        # Current mode
        self.current_mode = self.MODE_CLICK
        
        # Canvas properties
        self.canvas_width = 1200
        self.canvas_height = 675
        self.scale = 50
        
        # Zoom and pan properties
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.min_zoom = 0.2
        self.max_zoom = 5.0
        self.zoom_step = 0.1
        
        # Tracking state
        self.tracking_active = False
        
        # Drawing state
        self.is_drawing = False
        self.last_draw_point: Optional[Tuple[float, float]] = None
        self.draw_sample_distance = 15
        
        # Robot data
        self.robots: Dict[str, object] = {}
        self.robot_configs: Dict[str, Dict] = {}
        self.racing_configs: Dict[str, object] = {}
        self.robot_colors: Dict[str, str] = {}
        self.active_robot: Optional[str] = None
        
        # Robot state (thread-safe)
        self.robot_positions: Dict[str, Tuple[float, float, float]] = {}
        self.robot_states: Dict[str, Dict[str, float]] = {}
        self.follower_states: Dict[str, Dict[str, float]] = {}
        self.connection_status: Dict[str, object] = {}
        
        # Robot visuals
        self.robot_visuals: Dict[str, int] = {}
        
        # Settings
        self.estimated_delay_ms = 100
        self.use_prediction = True
    
    def get_robot_position(self, name: str) -> Tuple[float, float, float]:
        """Get robot position (thread-safe)."""
        with self._lock:
            return self.robot_positions.get(name, (0.0, 0.0, 0.0))
    
    def set_robot_position(self, name: str, x: float, y: float, yaw: float) -> None:
        """Set robot position (thread-safe)."""
        with self._lock:
            self.robot_positions[name] = (x, y, yaw)
    
    def update_robot_states(self, states: Dict[str, Dict]) -> None:
        """Update all robot states (thread-safe)."""
        with self._lock:
            self.robot_states = states
            for name, state in states.items():
                self.robot_positions[name] = (
                    state.get("x", 0.0),
                    state.get("y", 0.0),
                    state.get("yaw", 0.0),
                )
    
    def update_follower_states(self, states: Dict[str, Dict]) -> None:
        """Update path following states (thread-safe)."""
        with self._lock:
            self.follower_states = states
    
    def update_connection_status(self, status: Dict[str, object]) -> None:
        """Update connection status (thread-safe)."""
        with self._lock:
            self.connection_status = status
    
    def get_follower_states(self) -> Dict[str, Dict]:
        """Get copy of follower states (thread-safe)."""
        with self._lock:
            return dict(self.follower_states)
    
    def get_robot_positions(self) -> Dict[str, Tuple[float, float, float]]:
        """Get copy of all robot positions (thread-safe)."""
        with self._lock:
            return dict(self.robot_positions)

