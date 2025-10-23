#!/usr/bin/env python3
"""
UI Components
Reusable UI components for the robot controller.
"""

import tkinter as tk
from tkinter import ttk


class ModernButton(tk.Button):
    """Modern styled button component with proper dark mode support."""
    
    def __init__(self, parent, text, command=None, style="primary", **kwargs):
        # Define color schemes optimized for dark mode
        styles = {
            "primary": {
                "bg": "#2196F3", "fg": "#000000",  # Black text on blue
                "activebackground": "#1976D2", "activeforeground": "#000000",
                "disabledforeground": "#555555"  # Dark gray when disabled
            },
            "success": {
                "bg": "#4CAF50", "fg": "#000000",  # Black text on green
                "activebackground": "#388E3C", "activeforeground": "#000000",
                "disabledforeground": "#555555"
            },
            "warning": {
                "bg": "#FFA500", "fg": "#000000",  # Black text on orange
                "activebackground": "#F57C00", "activeforeground": "#000000",
                "disabledforeground": "#666666"
            },
            "danger": {
                "bg": "#f44336", "fg": "#000000",  # Black text on red
                "activebackground": "#D32F2F", "activeforeground": "#000000",
                "disabledforeground": "#555555"
            },
            "secondary": {
                "bg": "#555555", "fg": "#000000",  # Black text on dark gray
                "activebackground": "#666666", "activeforeground": "#000000",
                "disabledforeground": "#333333"
            }
        }
        
        style_config = styles.get(style, styles["secondary"])
        
        # Don't override fg if it's passed in kwargs
        if 'fg' not in kwargs and 'foreground' not in kwargs:
            style_config.update(kwargs)
        else:
            # If fg is passed, use it but keep other style properties
            temp_fg = kwargs.pop('fg', None) or kwargs.pop('foreground', None)
            style_config.update(kwargs)
            if temp_fg:
                style_config['fg'] = temp_fg
        
        super().__init__(
            parent, text=text, command=command,
            font=('Arial', 10, 'bold'), relief=tk.FLAT,
            cursor='hand2', borderwidth=0, 
            highlightthickness=0, **style_config
        )


class StatusLabel(tk.Label):
    """Status label with predefined styles."""
    
    def __init__(self, parent, text="", status="neutral", **kwargs):
        styles = {
            "success": {"fg": "#00ff88"},
            "warning": {"fg": "#ffaa00"},
            "error": {"fg": "#f44336"},
            "info": {"fg": "#00aaff"},
            "neutral": {"fg": "#888"}
        }
        
        style_config = styles.get(status, styles["neutral"])
        style_config.update(kwargs)
        
        super().__init__(
            parent, text=text, font=('Arial', 10, 'bold'),
            bg='#1a1a1a', **style_config
        )


class ModernFrame(tk.Frame):
    """Modern styled frame with optional title."""
    
    def __init__(self, parent, title=None, **kwargs):
        if title:
            self.frame = tk.LabelFrame(
                parent, text=title, font=('Arial', 10, 'bold'),
                bg='#1a1a1a', fg='#00ff88', bd=2, relief=tk.GROOVE
            )
        else:
            self.frame = tk.Frame(parent, bg='#1a1a1a')
        
        super().__init__(self.frame, **kwargs)
        self.configure(bg='#1a1a1a')
    
    def pack(self, **kwargs):
        """Pack the frame."""
        self.frame.pack(**kwargs)
        super().pack(fill=tk.BOTH, expand=True)


class ModernScale(tk.Scale):
    """Modern styled scale widget."""
    
    def __init__(self, parent, **kwargs):
        default_config = {
            "bg": "#2a2a2a", "fg": "#fff", "highlightthickness": 0,
            "troughcolor": "#0a0a0a", "activebackground": "#00ff88",
            "sliderrelief": tk.FLAT
        }
        default_config.update(kwargs)
        
        super().__init__(parent, **default_config)


class ModernCheckbutton(tk.Checkbutton):
    """Modern styled checkbutton."""
    
    def __init__(self, parent, **kwargs):
        default_config = {
            "bg": "#1a1a1a", "fg": "#ccc", "selectcolor": "#2a2a2a",
            "activebackground": "#1a1a1a", "activeforeground": "#00ff88",
            "cursor": "hand2"
        }
        default_config.update(kwargs)
        
        super().__init__(parent, **default_config)


class CanvasGrid:
    """Helper class for drawing grids on canvas."""
    
    def __init__(self, canvas, scale=100, width=700, height=700):
        self.canvas = canvas
        self.scale = scale
        self.width = width
        self.height = height
    
    def draw_grid(self):
        """Draw modern grid on canvas."""
        # Grid lines
        for i in range(0, self.width + 1, self.scale):
            # Darker grid lines
            color = '#1a1a1a' if i % (self.scale * 2) != 0 else '#2a2a2a'
            width = 1 if i % (self.scale * 2) != 0 else 2
            self.canvas.create_line(i, 0, i, self.height, fill=color, width=width, tags='grid')
            if i % self.scale == 0:
                self.canvas.create_text(i, self.height - 12,
                                      text=f"{i//self.scale}m", fill='#444', font=('Arial', 8))
        
        for i in range(0, self.height + 1, self.scale):
            color = '#1a1a1a' if i % (self.scale * 2) != 0 else '#2a2a2a'
            width = 1 if i % (self.scale * 2) != 0 else 2
            self.canvas.create_line(0, i, self.width, i, fill=color, width=width, tags='grid')
            if i % self.scale == 0:
                self.canvas.create_text(12, i, text=f"{i//self.scale}m", fill='#444', font=('Arial', 8))
        
        # Origin marker
        self.canvas.create_oval(
            self.width//2 - 6, self.height//2 - 6,
            self.width//2 + 6, self.height//2 + 6,
            fill='#00ff88', outline='#fff', width=2, tags='origin'
        )
        self.canvas.create_text(
            self.width//2, self.height//2 - 15,
            text="ORIGIN", fill='#00ff88', font=('Arial', 8, 'bold'), tags='origin'
        )
