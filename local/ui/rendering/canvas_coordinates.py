#!/usr/bin/env python3
"""
Canvas Coordinate Conversion
Utilities for converting between world and canvas coordinates with zoom and pan support.
"""

from typing import Tuple


class CanvasCoordinates:
    """Handles coordinate conversion between world (meters) and canvas (pixels) with zoom/pan."""
    
    def __init__(self, canvas_width: int, canvas_height: int, scale: float):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.scale = scale
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
    
    def world_to_canvas(self, x_m: float, y_m: float) -> Tuple[float, float]:
        """Convert world coordinates (meters) to canvas coordinates (pixels) with zoom/pan."""
        # First apply scale to convert meters to base pixels
        x_base = x_m * self.scale
        y_base = y_m * self.scale
        
        # Apply zoom
        x_zoomed = x_base * self.zoom
        y_zoomed = y_base * self.zoom
        
        # Apply pan offset and center on canvas
        x = x_zoomed + self.canvas_width / 2 + self.pan_x
        y = y_zoomed + self.canvas_height / 2 + self.pan_y
        
        return x, y
    
    def canvas_to_world(self, x: float, y: float) -> Tuple[float, float]:
        """Convert canvas coordinates (pixels) to world coordinates (meters) with zoom/pan."""
        # Remove canvas center offset and pan
        x_relative = x - self.canvas_width / 2 - self.pan_x
        y_relative = y - self.canvas_height / 2 - self.pan_y
        
        # Remove zoom
        x_base = x_relative / self.zoom
        y_base = y_relative / self.zoom
        
        # Convert from pixels to meters
        x_m = x_base / self.scale
        y_m = y_base / self.scale
        
        return x_m, y_m
    
    def update_dimensions(self, canvas_width: int, canvas_height: int) -> None:
        """Update canvas dimensions."""
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
    
    def set_zoom(self, zoom: float) -> None:
        """Set zoom level."""
        self.zoom = zoom
    
    def set_pan(self, pan_x: float, pan_y: float) -> None:
        """Set pan offset."""
        self.pan_x = pan_x
        self.pan_y = pan_y
    
    def update_transform(self, zoom: float, pan_x: float, pan_y: float) -> None:
        """Update both zoom and pan together."""
        self.zoom = zoom
        self.pan_x = pan_x
        self.pan_y = pan_y

