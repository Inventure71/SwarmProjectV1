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
                "bg": "#ef5350", "fg": "#000000",
                "activebackground": "#e53935", "activeforeground": "#000000",
                "disabledforeground": "#666666"
            },
            "secondary": {
                "bg": "#424242", "fg": "#000000",
                "activebackground": "#616161", "activeforeground": "#000000",
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
        
        # Ensure foreground is always black initially
        self.config(fg="#000000", activeforeground="#000000")
        
        # Add hover effect and event bindings
        self._bind_hover()
        self._bind_click_events()
    
    def _bind_hover(self):
        """Add hover effects."""
        self._original_bg = self.cget('bg')
        # Always use black for foreground
        self._original_fg = "#000000"
        
        def on_enter(e):
            if self.cget('state') != 'disabled':
                self.config(
                    bg=self._styles[self._current_style].get('activebackground', self._original_bg),
                    fg="#000000",  # Always black text on hover
                    activeforeground="#000000"
                )
        
        def on_leave(e):
            if self.cget('state') != 'disabled':
                self.config(
                    bg=self._original_bg,
                    fg="#000000",  # Always black text when not hovered
                    activeforeground="#000000"
                )
        
        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)
    
    def _bind_click_events(self):
        """Bind click and focus events to maintain black text."""
        def ensure_black_text():
            """Helper to ensure text is always black."""
            if self.cget('state') != 'disabled':
                current_fg = self.cget('fg')
                if current_fg != "#000000":
                    self.config(fg="#000000", activeforeground="#000000")
        
        def on_button_press(e):
            """Ensure black text when button is pressed."""
            ensure_black_text()
        
        def on_button_release(e):
            """Ensure black text when button is released."""
            ensure_black_text()
            # Also check after a short delay to catch any delayed color changes
            self.after(10, ensure_black_text)
        
        def on_focus_in(e):
            """Ensure black text when button gains focus."""
            ensure_black_text()
        
        def on_focus_out(e):
            """Ensure black text when button loses focus."""
            ensure_black_text()
            # Check again after focus loss to catch any delayed changes
            self.after(10, ensure_black_text)
        
        self.bind("<Button-1>", on_button_press)
        self.bind("<ButtonRelease-1>", on_button_release)
        self.bind("<FocusIn>", on_focus_in)
        self.bind("<FocusOut>", on_focus_out)
        
        # Also bind to mouse leave/enter to catch any color changes
        self.bind("<Enter>", lambda e: ensure_black_text(), add="+")
        self.bind("<Leave>", lambda e: ensure_black_text(), add="+")
        
        # Periodically check and fix text color (as a safety net)
        self._schedule_color_check()
    
    def _schedule_color_check(self):
        """Periodically check and fix button text color."""
        try:
            if self.winfo_exists() and self.cget('state') != 'disabled':
                current_fg = self.cget('fg')
                if current_fg and current_fg != "#000000" and current_fg != "#666666":  # Allow disabled gray
                    self.config(fg="#000000", activeforeground="#000000")
                # Check again after 500ms (less frequent to avoid performance issues)
                self.after(500, self._schedule_color_check)
        except:
            # Widget destroyed, stop checking
            pass
    
    def set_custom_color(self, bg_color, fg_color=None):
        """Set custom background and foreground colors, updating hover effects."""
        self._original_bg = bg_color
        # Always use black text
        self._original_fg = "#000000"
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
        # Apply colors - always use black text
        config = {
            'bg': bg_color,
            'fg': "#000000",  # Always black text
            'activeforeground': "#000000",  # Always black text on hover/active
            'disabledbackground': bg_color,  # Show color even when disabled
            'disabledforeground': "#666666"  # Gray when disabled
        }
        super().configure(**config)
        # Force update to ensure colors are applied
        self.update_idletasks()

    def set_style(self, style):
        """Apply one of the predefined styles dynamically."""
        if style not in self._styles:
            style = "secondary"
        self._current_style = style
        style_config = dict(self._styles[style])
        # Ensure foreground is always black
        style_config["fg"] = "#000000"
        style_config["activeforeground"] = "#000000"
        super().configure(**style_config)

    def configure(self, cnf=None, **kwargs):
        style = None
        if cnf and isinstance(cnf, dict) and 'style' in cnf:
            style = cnf.pop('style')
        if 'style' in kwargs:
            style = kwargs.pop('style')
        
        # Always ensure foreground is black unless explicitly overridden
        if cnf and isinstance(cnf, dict):
            if 'fg' not in cnf and 'foreground' not in cnf:
                cnf['fg'] = "#000000"
            if 'activeforeground' not in cnf:
                cnf['activeforeground'] = "#000000"
        else:
            if 'fg' not in kwargs and 'foreground' not in kwargs:
                kwargs['fg'] = "#000000"
            if 'activeforeground' not in kwargs:
                kwargs['activeforeground'] = "#000000"
        
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
    """Helper class for drawing modern grids on canvas with zoom/pan support."""
    
    def __init__(self, canvas, scale=100, width=700, height=700, coordinate_converter=None):
        self.canvas = canvas
        self.scale = scale
        self.width = width
        self.height = height
        self.coordinate_converter = coordinate_converter
    
    def draw_grid(self):
        """Draw modern grid on canvas with enhanced styling and zoom/pan support."""
        # Clear old grid
        self.canvas.delete('grid')
        self.canvas.delete('origin')
        
        if self.coordinate_converter is None:
            self._draw_simple_grid()
        else:
            self._draw_transformed_grid()
    
    def _draw_simple_grid(self):
        """Draw simple grid without transformation (fallback)."""
        # Grid lines with better colors
        for i in range(0, self.width + 1, self.scale):
            color = '#1a1a1a' if i % (self.scale * 2) != 0 else '#2a2a2a'
            width = 1 if i % (self.scale * 2) != 0 else 2
            self.canvas.create_line(i, 0, i, self.height, fill=color, width=width, tags='grid')
        
        for i in range(0, self.height + 1, self.scale):
            color = '#1a1a1a' if i % (self.scale * 2) != 0 else '#2a2a2a'
            width = 1 if i % (self.scale * 2) != 0 else 2
            self.canvas.create_line(0, i, self.width, i, fill=color, width=width, tags='grid')
        
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
    
    def _draw_transformed_grid(self):
        """Draw grid with zoom and pan transformation."""
        zoom = self.coordinate_converter.zoom
        
        # Calculate grid spacing in world coordinates (meters)
        grid_spacing_meters = 1.0  # 1 meter
        
        # Determine visible area in world coordinates
        top_left_world = self.coordinate_converter.canvas_to_world(0, 0)
        bottom_right_world = self.coordinate_converter.canvas_to_world(self.width, self.height)
        
        min_x_world = min(top_left_world[0], bottom_right_world[0])
        max_x_world = max(top_left_world[0], bottom_right_world[0])
        min_y_world = min(top_left_world[1], bottom_right_world[1])
        max_y_world = max(top_left_world[1], bottom_right_world[1])
        
        # Extend range slightly to ensure coverage
        min_x_world -= 2
        max_x_world += 2
        min_y_world -= 2
        max_y_world += 2
        
        # Draw vertical grid lines
        x_world = int(min_x_world / grid_spacing_meters) * grid_spacing_meters
        while x_world <= max_x_world:
            x_canvas, _ = self.coordinate_converter.world_to_canvas(x_world, 0)
            
            # Determine line style
            is_major = abs(x_world) < 0.01 or abs(x_world % 2.0) < 0.01
            color = '#2a2a2a' if is_major else '#1a1a1a'
            width = 2 if is_major else 1
            
            self.canvas.create_line(x_canvas, 0, x_canvas, self.height, 
                                   fill=color, width=width, tags='grid')
            
            # Add labels for major lines if zoom is reasonable
            if is_major and zoom > 0.3:
                self.canvas.create_text(
                    x_canvas, self.height - 12,
                    text=f"{int(x_world)}m", fill='#555', font=('Segoe UI', 8),
                    tags='grid'
                )
            
            x_world += grid_spacing_meters
        
        # Draw horizontal grid lines
        y_world = int(min_y_world / grid_spacing_meters) * grid_spacing_meters
        while y_world <= max_y_world:
            _, y_canvas = self.coordinate_converter.world_to_canvas(0, y_world)
            
            # Determine line style
            is_major = abs(y_world) < 0.01 or abs(y_world % 2.0) < 0.01
            color = '#2a2a2a' if is_major else '#1a1a1a'
            width = 2 if is_major else 1
            
            self.canvas.create_line(0, y_canvas, self.width, y_canvas,
                                   fill=color, width=width, tags='grid')
            
            # Add labels for major lines if zoom is reasonable
            if is_major and zoom > 0.3:
                self.canvas.create_text(
                    12, y_canvas,
                    text=f"{int(y_world)}m", fill='#555', font=('Segoe UI', 8),
                    tags='grid'
                )
            
            y_world += grid_spacing_meters
        
        # Draw origin marker
        origin_x, origin_y = self.coordinate_converter.world_to_canvas(0, 0)
        
        # Only draw origin if it's visible
        if 0 <= origin_x <= self.width and 0 <= origin_y <= self.height:
            marker_size = max(8, min(16, int(8 * zoom)))
            self.canvas.create_oval(
                origin_x - marker_size, origin_y - marker_size,
                origin_x + marker_size, origin_y + marker_size,
                fill='#00d4aa', outline='#ffffff', width=2, tags='origin'
            )
            if zoom > 0.5:
                self.canvas.create_text(
                    origin_x, origin_y - marker_size - 12,
                    text="ORIGIN", fill='#00d4aa', font=('Segoe UI', 9, 'bold'), tags='origin'
                )
