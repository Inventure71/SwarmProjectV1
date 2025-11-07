#!/usr/bin/env python3
"""
Path Planning Tab
Path creation and management interface.
"""

import tkinter as tk
from ui.components import ModernButton
from ui.tabbed_interface import CollapsibleSection


class PathPlanningTab:
    """Path planning tab for path management."""
    
    def __init__(self, parent, button_handler):
        self.button_handler = button_handler
        self.frame = parent
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup path planning tab UI."""
        # Use grid layout
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable content
        path_canvas = tk.Canvas(self.frame, bg="#0f0f0f", highlightthickness=0)
        path_scrollbar = tk.Scrollbar(self.frame, orient=tk.VERTICAL, command=path_canvas.yview)
        path_content = tk.Frame(path_canvas, bg="#0f0f0f")
        
        path_content.bind("<Configure>", lambda e: path_canvas.configure(scrollregion=path_canvas.bbox("all")))
        path_canvas.create_window((0, 0), window=path_content, anchor="nw")
        path_canvas.configure(yscrollcommand=path_scrollbar.set)
        
        path_canvas.grid(row=0, column=0, sticky="nsew")
        path_scrollbar.grid(row=0, column=1, sticky="ns")
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Path Management Section
        path_mgmt_section = CollapsibleSection(path_content, "📁 Path Management", bg="#1e1e1e", expanded=True)
        path_mgmt_section.pack(fill=tk.X, padx=15, pady=15)
        
        path_btn_frame = tk.Frame(path_mgmt_section.content, bg="#1e1e1e")
        path_btn_frame.pack(fill=tk.X, padx=15, pady=15)
        
        self.save_btn = ModernButton(path_btn_frame, text="💾 Save Path", style="primary", command=self.button_handler.save_path)
        self.save_btn.pack(side=tk.LEFT, padx=8, pady=8, fill=tk.X, expand=True)
        
        self.load_btn = ModernButton(path_btn_frame, text="📂 Load Path", style="primary", command=self.button_handler.load_path)
        self.load_btn.pack(side=tk.LEFT, padx=8, pady=8, fill=tk.X, expand=True)
        
        self.clear_btn = ModernButton(path_btn_frame, text="🗑 Clear Path", style="warning", command=self.button_handler.clear_path)
        self.clear_btn.pack(side=tk.LEFT, padx=8, pady=8, fill=tk.X, expand=True)
        
        # Path Info Section
        path_info_section = CollapsibleSection(path_content, "ℹ️ Path Information", bg="#1e1e1e", expanded=True)
        path_info_section.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        info_display = tk.Frame(path_info_section.content, bg="#1e1e1e")
        info_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        self.path_info_label = tk.Label(
            info_display,
            text="No path loaded",
            font=("Segoe UI", 11),
            bg="#1e1e1e",
            fg="#e0e0e0",
            justify=tk.LEFT,
            anchor=tk.NW,
            wraplength=600,
        )
        self.path_info_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            path_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        path_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def update_path_info(self, info_text: str):
        """Update path information display."""
        self.path_info_label.config(text=info_text)

