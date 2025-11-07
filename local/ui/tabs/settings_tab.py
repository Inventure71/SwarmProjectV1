#!/usr/bin/env python3
"""
Settings Tab
Application settings interface.
"""

import tkinter as tk
from ui.components import ModernScale, ModernCheckbutton
from ui.tabbed_interface import CollapsibleSection


class SettingsTab:
    """Settings tab for application configuration."""
    
    def __init__(self, parent, state, on_change_callback):
        self.state = state
        self.on_change = on_change_callback
        self.frame = parent
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup settings tab UI."""
        # Use grid layout
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Scrollable content
        settings_canvas = tk.Canvas(self.frame, bg="#0f0f0f", highlightthickness=0)
        settings_scrollbar = tk.Scrollbar(self.frame, orient=tk.VERTICAL, command=settings_canvas.yview)
        settings_content = tk.Frame(settings_canvas, bg="#0f0f0f")
        
        settings_content.bind("<Configure>", lambda e: settings_canvas.configure(scrollregion=settings_canvas.bbox("all")))
        settings_canvas.create_window((0, 0), window=settings_content, anchor="nw")
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        
        settings_canvas.grid(row=0, column=0, sticky="nsew")
        settings_scrollbar.grid(row=0, column=1, sticky="ns")
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Prediction Settings Section
        prediction_section = CollapsibleSection(settings_content, "🔮 Position Prediction", bg="#1e1e1e", expanded=True)
        prediction_section.pack(fill=tk.X, padx=15, pady=15)
        
        delay_container = tk.Frame(prediction_section.content, bg="#1e1e1e")
        delay_container.pack(fill=tk.X, padx=15, pady=15)
        tk.Label(delay_container, text="Prediction Delay:", bg="#1e1e1e", fg="#e0e0e0", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        delay_control = tk.Frame(delay_container, bg="#1e1e1e")
        delay_control.pack(fill=tk.X, pady=5)
        
        self.delay_var = tk.IntVar(value=self.state.estimated_delay_ms)
        delay_slider = ModernScale(
            delay_control,
            from_=0,
            to=300,
            orient=tk.HORIZONTAL,
            variable=self.delay_var,
            command=self._on_delay_change,
        )
        delay_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.delay_label = tk.Label(
            delay_control,
            text=f"{self.state.estimated_delay_ms}ms",
            bg="#1e1e1e",
            fg="#00d4aa",
            font=("Segoe UI", 10, "bold"),
            width=8,
        )
        self.delay_label.pack(side=tk.LEFT, padx=10)
        
        self.prediction_var = tk.BooleanVar(value=self.state.use_prediction)
        prediction_check = ModernCheckbutton(
            prediction_section.content,
            text="Enable Position Prediction",
            variable=self.prediction_var,
            command=self._on_prediction_change,
        )
        prediction_check.pack(anchor=tk.W, padx=15, pady=10)
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        settings_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def _on_delay_change(self, value):
        """Handle delay change."""
        self.state.estimated_delay_ms = int(value)
        self.delay_label.config(text=f"{self.state.estimated_delay_ms}ms")
        self.on_change("delay")
    
    def _on_prediction_change(self):
        """Handle prediction change."""
        self.state.use_prediction = self.prediction_var.get()
        self.on_change("prediction")

