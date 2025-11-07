#!/usr/bin/env python3
"""
Canvas Zoom and Pan Handler
Handles mouse wheel zoom and right-click pan interactions.
"""

import tkinter as tk


class CanvasZoomPanHandler:
    """Handles zoom and pan interactions on the canvas."""
    
    def __init__(self, canvas: tk.Canvas, state, coordinates, on_transform_change):
        self.canvas = canvas
        self.state = state
        self.coordinates = coordinates
        self.on_transform_change = on_transform_change
        
        # Pan state
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.pan_start_offset_x = 0
        self.pan_start_offset_y = 0
        
        # Bind events
        self._bind_events()
    
    def _bind_events(self):
        """Bind mouse events for zoom and pan."""
        # Mouse wheel for zoom (cross-platform)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel, add="+")  # Windows/Mac
        self.canvas.bind("<Button-4>", self._on_mouse_wheel, add="+")    # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_mouse_wheel, add="+")    # Linux scroll down
        
        # Right-click for pan
        self.canvas.bind("<Button-3>", self._on_pan_start, add="+")
        self.canvas.bind("<B3-Motion>", self._on_pan_drag, add="+")
        self.canvas.bind("<ButtonRelease-3>", self._on_pan_end, add="+")
    
    def _on_mouse_wheel(self, event):
        """Handle mouse wheel zoom."""
        # Get mouse position on canvas
        mouse_x = event.x
        mouse_y = event.y
        
        # Determine zoom direction
        if event.num == 4 or event.delta > 0:  # Scroll up - zoom in
            zoom_factor = 1.0 + self.state.zoom_step
        elif event.num == 5 or event.delta < 0:  # Scroll down - zoom out
            zoom_factor = 1.0 - self.state.zoom_step
        else:
            return
        
        # Calculate new zoom level
        new_zoom = self.state.zoom * zoom_factor
        
        # Clamp zoom to min/max
        new_zoom = max(self.state.min_zoom, min(self.state.max_zoom, new_zoom))
        
        if new_zoom == self.state.zoom:
            return  # No change
        
        # Zoom towards mouse cursor
        # Convert mouse position to world coordinates with current zoom
        world_x, world_y = self.coordinates.canvas_to_world(mouse_x, mouse_y)
        
        # Update zoom
        old_zoom = self.state.zoom
        self.state.zoom = new_zoom
        self.coordinates.set_zoom(new_zoom)
        
        # Calculate new mouse position in canvas after zoom
        new_mouse_x, new_mouse_y = self.coordinates.world_to_canvas(world_x, world_y)
        
        # Adjust pan to keep world point under mouse
        pan_adjust_x = mouse_x - new_mouse_x
        pan_adjust_y = mouse_y - new_mouse_y
        
        self.state.pan_x += pan_adjust_x
        self.state.pan_y += pan_adjust_y
        self.coordinates.set_pan(self.state.pan_x, self.state.pan_y)
        
        # Notify about transform change
        self.on_transform_change()
    
    def _on_pan_start(self, event):
        """Start panning."""
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.pan_start_offset_x = self.state.pan_x
        self.pan_start_offset_y = self.state.pan_y
        
        # Change cursor to indicate panning
        self.canvas.config(cursor="fleur")
    
    def _on_pan_drag(self, event):
        """Handle pan dragging."""
        if not self.is_panning:
            return
        
        # Calculate pan offset
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        
        # Update pan
        self.state.pan_x = self.pan_start_offset_x + dx
        self.state.pan_y = self.pan_start_offset_y + dy
        self.coordinates.set_pan(self.state.pan_x, self.state.pan_y)
        
        # Notify about transform change
        self.on_transform_change()
    
    def _on_pan_end(self, event):
        """End panning."""
        self.is_panning = False
        
        # Restore cursor
        self.canvas.config(cursor="")
    
    def reset_view(self):
        """Reset zoom and pan to default."""
        self.state.zoom = 1.0
        self.state.pan_x = 0.0
        self.state.pan_y = 0.0
        self.coordinates.update_transform(1.0, 0.0, 0.0)
        self.on_transform_change()

