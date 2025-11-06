#!/usr/bin/env python3
"""
Tabbed Interface Components - Enhanced with Modern Design
Modern tabbed interface for organizing UI sections with beautiful styling.
"""

import tkinter as tk
import sys
from typing import Optional


class TabButton(tk.Button):
    """Modern tab button for navigation with enhanced styling."""
    
    def __init__(self, parent, text, command=None, **kwargs):
        # Use system default font to avoid parsing issues
        # On macOS, use Helvetica; on Windows/Linux, use Arial
        if sys.platform == "darwin":
            btn_font = ("Helvetica", 11, "bold")
        else:
            btn_font = ("Arial", 11, "bold")
        
        default_config = {
            "bg": "#2d2d2d",
            "fg": "#b0b0b0",
            "activebackground": "#3a3a3a",
            "activeforeground": "#ffffff",
            "relief": tk.FLAT,
            "borderwidth": 0,
            "padx": 24,
            "pady": 14,
            "cursor": "hand2",
            "highlightthickness": 0,
            "bd": 0,
        }
        # Set font separately to avoid parsing issues
        default_config.update(kwargs)
        super().__init__(parent, text=text, command=command, **default_config)
        # Configure font after creation
        self.config(font=btn_font)
        self._is_active = False
        self._btn_font = btn_font
        self._bind_hover()
    
    def _bind_hover(self):
        """Bind hover effects."""
        self.bind("<Enter>", lambda e: self._on_enter())
        self.bind("<Leave>", lambda e: self._on_leave())
    
    def _on_enter(self):
        """Handle mouse enter."""
        if not self._is_active:
            self.config(bg="#353535", fg="#ffffff")
    
    def _on_leave(self):
        """Handle mouse leave."""
        if not self._is_active:
            self.config(bg="#2d2d2d", fg="#b0b0b0")
    
    def set_active(self, active: bool):
        """Set active state."""
        self._is_active = active
        if active:
            self.config(
                bg="#00d4aa",
                fg="#000000",
                relief=tk.FLAT,
                font=self._btn_font
            )
        else:
            self.config(
                bg="#2d2d2d",
                fg="#b0b0b0",
                relief=tk.FLAT,
                font=self._btn_font
            )


class CollapsibleSection:
    """Enhanced collapsible section widget with modern styling."""
    
    def __init__(self, parent, title: str, bg="#1e1e1e", expanded=True):
        self.parent = parent
        self.title = title
        self.bg = bg
        self.is_expanded = expanded
        
        # Use system default fonts to avoid parsing issues
        if sys.platform == "darwin":
            toggle_font = ("Helvetica", 12, "bold")
            title_font = ("Helvetica", 10, "bold")
        else:
            toggle_font = ("Arial", 12, "bold")
            title_font = ("Arial", 10, "bold")
        
        # Container frame with modern styling
        self.container = tk.Frame(
            parent,
            bg=bg,
            relief=tk.FLAT,
            bd=0,
            highlightbackground="#333333",
            highlightthickness=1
        )
        
        # Header frame with hover effect
        self.header = tk.Frame(self.container, bg="#252525", cursor="hand2")
        self.header.pack(fill=tk.X)
        self.header.bind("<Button-1>", lambda e: self.toggle())
        
        # Toggle button with better styling
        self.toggle_btn = tk.Label(
            self.header,
            text="▼" if self.is_expanded else "▶",
            bg="#252525",
            fg="#00d4aa",
            font=toggle_font,
            width=3,
            cursor="hand2",
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=8, pady=10)
        self.toggle_btn.bind("<Button-1>", lambda e: self.toggle())
        
        # Title label with better styling
        self.title_label = tk.Label(
            self.header,
            text=title,
            bg="#252525",
            fg="#ffffff",
            font=title_font,
            anchor=tk.W,
            cursor="hand2",
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), pady=10)
        self.title_label.bind("<Button-1>", lambda e: self.toggle())
        
        # Content frame
        self.content = tk.Frame(self.container, bg=bg)
        if self.is_expanded:
            self.content.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        else:
            self.content.pack_forget()
        
        # Hover effect for header
        self._bind_hover()
    
    def _bind_hover(self):
        """Bind hover effects to header."""
        for widget in [self.header, self.toggle_btn, self.title_label]:
            widget.bind("<Enter>", lambda e: self._on_enter())
            widget.bind("<Leave>", lambda e: self._on_leave())
    
    def _on_enter(self):
        """Handle mouse enter."""
        self.header.config(bg="#2a2a2a")
        self.toggle_btn.config(bg="#2a2a2a")
        self.title_label.config(bg="#2a2a2a")
    
    def _on_leave(self):
        """Handle mouse leave."""
        self.header.config(bg="#252525")
        self.toggle_btn.config(bg="#252525")
        self.title_label.config(bg="#252525")
    
    def toggle(self):
        """Toggle expanded/collapsed state."""
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.content.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            self.toggle_btn.config(text="▼")
        else:
            self.content.pack_forget()
            self.toggle_btn.config(text="▶")
    
    def pack(self, **kwargs):
        """Pack the container."""
        self.container.pack(**kwargs)
    
    def pack_forget(self):
        """Hide the container."""
        self.container.pack_forget()


class TabbedInterface:
    """Enhanced tabbed interface container with modern design."""
    
    def __init__(self, parent, bg="#0f0f0f"):
        self.parent = parent
        self.bg = bg
        self.tabs: dict[str, tuple[TabButton, tk.Frame]] = {}
        self.current_tab: Optional[str] = None
        
        # Enhanced tab bar container with better styling
        self.tab_bar = tk.Frame(parent, bg="#1a1a1a", height=55)
        self.tab_bar.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0)
        self.tab_bar.pack_propagate(False)
        
        # Content container
        self.content_area = tk.Frame(parent, bg=bg)
        self.content_area.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        # Configure grid so tab content frames can overlap in same cell
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)
    
    def add_tab(self, name: str, icon: str = "") -> tk.Frame:
        """Add a new tab and return its content frame."""
        tab_text = f"{icon} {name}" if icon else name
        
        # Create tab button
        tab_btn = TabButton(
            self.tab_bar,
            text=tab_text,
            command=lambda: self.switch_tab(name),
        )
        tab_btn.pack(side=tk.LEFT, padx=1, pady=0)
        
        # Create content frame (grid into same cell for overlap; we will raise on switch)
        content_frame = tk.Frame(self.content_area, bg=self.bg)
        content_frame.grid(row=0, column=0, sticky="nsew")
        
        # Store tab info
        self.tabs[name] = (tab_btn, content_frame)
        
        # Set first tab as active (raise without repacking others)
        if self.current_tab is None:
            self.switch_tab(name)
        
        return content_frame
    
    def switch_tab(self, name: str):
        """Switch to a different tab."""
        if name not in self.tabs:
            return
        # No-op if already current
        if self.current_tab == name:
            return
        
        # Update previous tab button state (content remains packed; we use stacking)
        if self.current_tab:
            old_btn, _ = self.tabs[self.current_tab]
            old_btn.set_active(False)
        
        # Show new tab content by raising (instant switch)
        new_btn, new_content = self.tabs[name]
        try:
            new_content.tkraise()
        except Exception:
            pass
        self.content_area.update_idletasks()
        new_btn.set_active(True)
        
        self.current_tab = name
    
    def get_current_frame(self) -> Optional[tk.Frame]:
        """Get the current tab's content frame."""
        if self.current_tab:
            return self.tabs[self.current_tab][1]
        return None
