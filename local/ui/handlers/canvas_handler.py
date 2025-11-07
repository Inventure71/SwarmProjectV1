#!/usr/bin/env python3
"""
Canvas Event Handler
Handles mouse events on the canvas for path creation.
"""

import math


class CanvasHandler:
    """Handles canvas mouse events for waypoint creation."""
    
    def __init__(self, state, path_service, update_callback):
        self.state = state
        self.path_service = path_service
        self.update_callback = update_callback
    
    def on_click(self, event):
        """Handle canvas click event."""
        if not self.state.tracking_active or self.state.current_mode == self.state.MODE_RECORD:
            return
        
        x, y = event.x, event.y
        
        if self.state.current_mode == self.state.MODE_DRAW:
            self.state.is_drawing = True
            self.state.last_draw_point = (x, y)
            self.path_service.add_waypoint(self.state.active_robot, x, y, "draw")
        else:
            self.path_service.add_waypoint(self.state.active_robot, x, y, "click")
        
        self.update_callback()
    
    def on_drag(self, event):
        """Handle canvas drag event."""
        if self.state.current_mode != self.state.MODE_DRAW or not self.state.is_drawing or not self.state.tracking_active:
            return
        
        x, y = event.x, event.y
        
        if self.state.last_draw_point is not None:
            dx = x - self.state.last_draw_point[0]
            dy = y - self.state.last_draw_point[1]
            dist = math.sqrt(dx ** 2 + dy ** 2)
            
            if dist >= self.state.draw_sample_distance:
                self.path_service.add_waypoint(self.state.active_robot, x, y, "draw")
                self.state.last_draw_point = (x, y)
                self.update_callback()
    
    def on_release(self, event):
        """Handle canvas mouse release event."""
        if self.state.current_mode == self.state.MODE_DRAW:
            self.state.is_drawing = False
            self.state.last_draw_point = None

