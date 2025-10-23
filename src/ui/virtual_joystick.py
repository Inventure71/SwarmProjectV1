#!/usr/bin/env python3
"""
Virtual Joystick Widget
A custom Tkinter widget for intuitive robot control.
"""

import tkinter as tk
import math


class VirtualJoystick(tk.Canvas):
    """Virtual joystick widget for intuitive robot control."""
    
    def __init__(self, parent, size=200, **kwargs):
        super().__init__(parent, width=size, height=size, bg='#1a1a1a', 
                        highlightthickness=2, highlightbackground='#444', **kwargs)
        self.size = size
        self.center_x = size // 2
        self.center_y = size // 2
        self.max_radius = size // 2 - 20
        
        self.joystick_x = 0.0  # -1.0 to 1.0
        self.joystick_y = 0.0  # -1.0 to 1.0
        
        self.dragging = False
        self.stick_handle = None
        
        self._draw_base()
        
        self.bind('<Button-1>', self._on_press)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)
        
    def _draw_base(self):
        """Draw joystick base."""
        # Outer circle
        self.create_oval(
            self.center_x - self.max_radius, self.center_y - self.max_radius,
            self.center_x + self.max_radius, self.center_y + self.max_radius,
            fill='#2a2a2a', outline='#555', width=2
        )
        
        # Center crosshair
        line_len = 15
        self.create_line(
            self.center_x - line_len, self.center_y,
            self.center_x + line_len, self.center_y,
            fill='#555', width=1
        )
        self.create_line(
            self.center_x, self.center_y - line_len,
            self.center_x, self.center_y + line_len,
            fill='#555', width=1
        )
        
        # Direction indicators
        self.create_text(self.center_x, 15, text="↑ FWD", fill='#888', font=('Arial', 9, 'bold'))
        self.create_text(self.center_x, self.size - 15, text="↓ REV", fill='#888', font=('Arial', 9, 'bold'))
        self.create_text(15, self.center_y, text="← L", fill='#888', font=('Arial', 9, 'bold'))
        self.create_text(self.size - 15, self.center_y, text="R →", fill='#888', font=('Arial', 9, 'bold'))
        
        # Stick handle
        self.stick_handle = self.create_oval(
            self.center_x - 20, self.center_y - 20,
            self.center_x + 20, self.center_y + 20,
            fill='#4CAF50', outline='#fff', width=3
        )
    
    def _on_press(self, event):
        """Handle mouse press."""
        self.dragging = True
        self._update_position(event.x, event.y)
    
    def _on_drag(self, event):
        """Handle mouse drag."""
        if self.dragging:
            self._update_position(event.x, event.y)
    
    def _on_release(self, event):
        """Handle mouse release - return to center."""
        self.dragging = False
        self.joystick_x = 0.0
        self.joystick_y = 0.0
        self._update_visual()
    
    def _update_position(self, x, y):
        """Update joystick position."""
        # Calculate offset from center
        dx = x - self.center_x
        dy = y - self.center_y
        
        # Calculate distance and constrain to max radius
        dist = math.sqrt(dx**2 + dy**2)
        if dist > self.max_radius:
            scale = self.max_radius / dist
            dx *= scale
            dy *= scale
            dist = self.max_radius
        
        # Convert to -1.0 to 1.0 range
        self.joystick_x = dx / self.max_radius
        self.joystick_y = -dy / self.max_radius  # Invert Y (screen coords)
        
        self._update_visual()
    
    def _update_visual(self):
        """Update visual position of stick."""
        # Calculate screen position
        x = self.center_x + self.joystick_x * self.max_radius
        y = self.center_y - self.joystick_y * self.max_radius
        
        # Update stick position
        self.coords(self.stick_handle, x - 20, y - 20, x + 20, y + 20)
    
    def get_values(self):
        """Get current joystick values.
        
        Returns:
            (x, y) tuple where both are in range [-1.0, 1.0]
            x: left/right (-1 = left, 1 = right)
            y: forward/back (-1 = back, 1 = forward)
        """
        return (self.joystick_x, self.joystick_y)
    
    def reset(self):
        """Reset joystick to center."""
        self.joystick_x = 0.0
        self.joystick_y = 0.0
        self._update_visual()

