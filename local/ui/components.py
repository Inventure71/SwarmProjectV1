#!/usr/bin/env python3
"""
UI Components - Enhanced with Modern Design
Reusable UI components for the robot controller with beautiful styling.
"""

import tkinter as tk
from tkinter import ttk


class ModernButton(tk.Button):
    """Modern styled button component with enhanced visual design."""
    
    def __init__(self, parent, text, command=None, style="primary", **kwargs):
        self._styles = {
            "primary": {
                "bg": "#00d4aa", "fg": "#000000",
                "activebackground": "#00b894", "activeforeground": "#000000",
                "disabledforeground": "#666666"
            },
            "success": {
                "bg": "#00d4aa", "fg": "#000000",
                "activebackground": "#00b894", "activeforeground": "#000000",
                "disabledforeground": "#666666"
            },
            "warning": {
                "bg": "#ffa726", "fg": "#000000",
                "activebackground": "#ff9800", "activeforeground": "#000000",
                "disabledforeground": "#666666"
            },
            "danger": {
                "bg": "#ef5350", "fg": "#ffffff",
                "activebackground": "#e53935", "activeforeground": "#ffffff",
                "disabledforeground": "#666666"
            },
            "secondary": {
                "bg": "#424242", "fg": "#ffffff",
                "activebackground": "#616161", "activeforeground": "#ffffff",
                "disabledforeground": "#666666"
            }
        }
        self._current_style = style if style in self._styles else "secondary"
        style_config = dict(self._styles[self._current_style])
        style_config.update(kwargs)
        
        default_font = kwargs.pop('font', ('Segoe UI', 10, 'bold'))
        
        super().__init__(
            parent, text=text, command=command,
            font=default_font, relief=tk.FLAT,
            cursor='hand2', borderwidth=0,
            highlightthickness=0, **style_config
        )
        
        # Add hover effect
        self._bind_hover()
    
    def _bind_hover(self):
        """Add hover effects."""
        self._original_bg = self.cget('bg')
        self._original_fg = self.cget('fg')
        
        def on_enter(e):
            if self.cget('state') != 'disabled':
                self.config(bg=self._styles[self._current_style].get('activebackground', self._original_bg))
        
        def on_leave(e):
            if self.cget('state') != 'disabled':
                self.config(bg=self._original_bg)
        
        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)
    
    def set_custom_color(self, bg_color, fg_color=None):
        """Set custom background and foreground colors, updating hover effects."""
        self._original_bg = bg_color
        if fg_color:
            self._original_fg = fg_color
        # Calculate darker shade for hover (reduce brightness by ~15%)
        try:
            r = int(bg_color[1:3], 16)
            g = int(bg_color[3:5], 16)
            b = int(bg_color[5:7], 16)
            hover_r = max(0, int(r * 0.85))
            hover_g = max(0, int(g * 0.85))
            hover_b = max(0, int(b * 0.85))
            hover_bg = f"#{hover_r:02x}{hover_g:02x}{hover_b:02x}"
        except Exception:
            hover_bg = bg_color
        # Update style dict temporarily
        self._styles[self._current_style]['activebackground'] = hover_bg
        # Apply colors - include disabled state colors
        config = {
            'bg': bg_color,
            'disabledbackground': bg_color,  # Show color even when disabled
        }
        if fg_color:
            config['fg'] = fg_color
            config['activeforeground'] = fg_color
            config['disabledforeground'] = fg_color  # Show text color even when disabled
        super().configure(**config)
        # Force update to ensure colors are applied
        self.update_idletasks()

    def set_style(self, style):
        """Apply one of the predefined styles dynamically."""
        if style not in self._styles:
            style = "secondary"
        self._current_style = style
        style_config = self._styles[style]
        super().configure(**style_config)

    def configure(self, cnf=None, **kwargs):
        style = None
        if cnf and isinstance(cnf, dict) and 'style' in cnf:
            style = cnf.pop('style')
        if 'style' in kwargs:
            style = kwargs.pop('style')
        result = super().configure(cnf, **kwargs)
        if style is not None:
            self.set_style(style)
        return result

    config = configure


class StatusLabel(tk.Label):
    """Status label with enhanced predefined styles."""
    
    def __init__(self, parent, text="", status="neutral", **kwargs):
        styles = {
            "success": {"fg": "#00d4aa"},
            "warning": {"fg": "#ffa726"},
            "error": {"fg": "#ef5350"},
            "info": {"fg": "#42a5f5"},
            "neutral": {"fg": "#9e9e9e"}
        }
        
        style_config = styles.get(status, styles["neutral"])
        style_config.update(kwargs)
        
        default_font = kwargs.pop('font', ('Segoe UI', 10, 'bold'))
        
        super().__init__(
            parent, text=text, font=default_font,
            bg='#1e1e1e', **style_config
        )


class ModernFrame(tk.Frame):
    """Modern styled frame with optional title."""
    
    def __init__(self, parent, title=None, **kwargs):
        if title:
            self.frame = tk.LabelFrame(
                parent, text=title, font=('Segoe UI', 10, 'bold'),
                bg='#1e1e1e', fg='#00d4aa', bd=1, relief=tk.FLAT,
                highlightbackground="#333333", highlightthickness=1
            )
        else:
            self.frame = tk.Frame(parent, bg='#1e1e1e')
        
        super().__init__(self.frame, **kwargs)
        self.configure(bg='#1e1e1e')
    
    def pack(self, **kwargs):
        """Pack the frame."""
        self.frame.pack(**kwargs)
        super().pack(fill=tk.BOTH, expand=True)


class ModernScale(tk.Scale):
    """Modern styled scale widget with enhanced design."""
    
    def __init__(self, parent, **kwargs):
        default_config = {
            "bg": "#2d2d2d", "fg": "#ffffff", "highlightthickness": 0,
            "troughcolor": "#1a1a1a", "activebackground": "#00d4aa",
            "sliderrelief": tk.FLAT, "orient": tk.HORIZONTAL,
            "length": 200
        }
        default_config.update(kwargs)
        
        super().__init__(parent, **default_config)


class ModernCheckbutton(tk.Checkbutton):
    """Modern styled checkbutton with enhanced design."""
    
    def __init__(self, parent, **kwargs):
        default_config = {
            "bg": "#1e1e1e", "fg": "#e0e0e0", "selectcolor": "#00d4aa",
            "activebackground": "#1e1e1e", "activeforeground": "#00d4aa",
            "cursor": "hand2", "font": ("Segoe UI", 10)
        }
        default_config.update(kwargs)
        
        super().__init__(parent, **default_config)


class CanvasGrid:
    """Helper class for drawing modern grids on canvas."""
    
    def __init__(self, canvas, scale=100, width=700, height=700):
        self.canvas = canvas
        self.scale = scale
        self.width = width
        self.height = height
    
    def draw_grid(self):
        """Draw modern grid on canvas with enhanced styling."""
        # Grid lines with better colors
        for i in range(0, self.width + 1, self.scale):
            color = '#1a1a1a' if i % (self.scale * 2) != 0 else '#2a2a2a'
            width = 1 if i % (self.scale * 2) != 0 else 2
            self.canvas.create_line(i, 0, i, self.height, fill=color, width=width, tags='grid')
            if i % self.scale == 0:
                self.canvas.create_text(
                    i, self.height - 12,
                    text=f"{i//self.scale}m", fill='#555', font=('Segoe UI', 8)
                )
        
        for i in range(0, self.height + 1, self.scale):
            color = '#1a1a1a' if i % (self.scale * 2) != 0 else '#2a2a2a'
            width = 1 if i % (self.scale * 2) != 0 else 2
            self.canvas.create_line(0, i, self.width, i, fill=color, width=width, tags='grid')
            if i % self.scale == 0:
                self.canvas.create_text(
                    12, i, text=f"{i//self.scale}m", fill='#555', font=('Segoe UI', 8)
                )
        
        # Enhanced origin marker
        center_x, center_y = self.width//2, self.height//2
        self.canvas.create_oval(
            center_x - 8, center_y - 8,
            center_x + 8, center_y + 8,
            fill='#00d4aa', outline='#ffffff', width=2, tags='origin'
        )
        self.canvas.create_text(
            center_x, center_y - 20,
            text="ORIGIN", fill='#00d4aa', font=('Segoe UI', 9, 'bold'), tags='origin'
        )
