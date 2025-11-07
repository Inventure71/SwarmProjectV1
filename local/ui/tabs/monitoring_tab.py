#!/usr/bin/env python3
"""
Monitoring Tab
Status and debug information interface.
"""

import tkinter as tk
from ui.components import StatusLabel
from ui.tabbed_interface import CollapsibleSection


class MonitoringTab:
    """Monitoring tab for status and debug information."""
    
    def __init__(self, parent):
        self.frame = parent
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup monitoring tab UI."""
        # Use grid layout
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable content
        monitoring_canvas = tk.Canvas(self.frame, bg="#0f0f0f", highlightthickness=0)
        monitoring_scrollbar = tk.Scrollbar(self.frame, orient=tk.VERTICAL, command=monitoring_canvas.yview)
        monitoring_content = tk.Frame(monitoring_canvas, bg="#0f0f0f")
        
        monitoring_content.bind("<Configure>", lambda e: monitoring_canvas.configure(scrollregion=monitoring_canvas.bbox("all")))
        monitoring_canvas.create_window((0, 0), window=monitoring_content, anchor="nw")
        monitoring_canvas.configure(yscrollcommand=monitoring_scrollbar.set)
        
        monitoring_canvas.grid(row=0, column=0, sticky="nsew")
        monitoring_scrollbar.grid(row=0, column=1, sticky="ns")
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Connection Status Section
        status_section = CollapsibleSection(monitoring_content, "📡 Connection Status", bg="#1e1e1e", expanded=True)
        status_section.pack(fill=tk.X, padx=15, pady=15)
        
        status_display = tk.Frame(status_section.content, bg="#1e1e1e")
        status_display.pack(fill=tk.X, padx=15, pady=15)
        
        self.monitoring_status_label = StatusLabel(status_display, text="⚪ Not Connected", fg="#9e9e9e")
        self.monitoring_status_label.pack(fill=tk.X, padx=10, pady=10)
        
        # Robot Positions Section
        positions_section = CollapsibleSection(monitoring_content, "📍 Robot Positions", bg="#1e1e1e", expanded=True)
        positions_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        positions_display = tk.Frame(positions_section.content, bg="#1e1e1e")
        positions_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.positions_label = tk.Label(
            positions_display,
            text="Position: Not tracking",
            font=("Segoe UI", 11),
            bg="#1e1e1e",
            fg="#00d4aa",
            justify=tk.LEFT,
            anchor=tk.NW,
            wraplength=700,
        )
        self.positions_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Debug Info Section
        debug_section = CollapsibleSection(monitoring_content, "🐛 Debug Information", bg="#1e1e1e", expanded=True)
        debug_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        debug_display = tk.Frame(debug_section.content, bg="#1e1e1e")
        debug_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.debug_label = tk.Label(
            debug_display,
            text="",
            font=("Segoe UI", 10),
            bg="#1e1e1e",
            fg="#e0e0e0",
            justify=tk.LEFT,
            anchor=tk.NW,
            wraplength=700,
        )
        self.debug_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            monitoring_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        monitoring_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def update_status(self, text: str, color: str):
        """Update connection status."""
        self.monitoring_status_label.config(text=text, fg=color)
    
    def update_positions(self, text: str):
        """Update robot positions display."""
        self.positions_label.config(text=text)
    
    def update_debug(self, text: str):
        """Update debug information."""
        self.debug_label.config(text=text)

