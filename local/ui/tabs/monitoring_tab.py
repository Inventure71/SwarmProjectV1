#!/usr/bin/env python3
"""
Monitoring Tab
Status and debug information interface.
"""

import math
import tkinter as tk
from tkinter import ttk
from ui.components import StatusLabel, ModernButton
from ui.tabbed_interface import CollapsibleSection


class RobotMonitorPanel:
    """Individual robot monitoring panel."""
    
    def __init__(self, parent, panel_id):
        self.panel_id = panel_id
        self.frame = tk.Frame(parent, bg="#1e1e1e", relief=tk.RAISED, borderwidth=2)
        self.selected_robot = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup panel UI."""
        # Header with robot selector - compact
        header = tk.Frame(self.frame, bg="#2d2d2d", height=28)
        header.pack(fill=tk.X, padx=1, pady=1)
        header.pack_propagate(False)
        
        tk.Label(header, text=f"#{self.panel_id}", bg="#2d2d2d", fg="#00d4aa", 
                font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=6, pady=2)
        
        self.robot_selector = ttk.Combobox(header, state="readonly", font=("Segoe UI", 9), width=8)
        self.robot_selector.pack(side=tk.RIGHT, padx=6, pady=2)
        self.robot_selector.bind("<<ComboboxSelected>>", self._on_robot_changed)
        
        # Content area - no scrollbar needed for compact layout
        self.content = tk.Frame(self.frame, bg="#1e1e1e")
        self.content.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Configure grid for 2-column layout
        self.content.grid_columnconfigure(0, weight=1, uniform="col")
        self.content.grid_columnconfigure(1, weight=1, uniform="col")
        
        # Info widgets in 2-column grid - larger text, compact spacing
        self.info_labels = {}
        self._create_compact_info("position", "📍 Pos", "N/A", 0, 0)
        self._create_compact_info("orientation", "🧭 Yaw", "N/A", 0, 1)
        self._create_compact_info("battery", "🔋 Bat", "N/A", 1, 0)
        self._create_compact_info("voltage", "⚡ V", "N/A", 1, 1)
        self._create_compact_info("status", "🎯 St", "N/A", 2, 0)
        self._create_compact_info("waypoint", "📍 WP", "N/A", 2, 1)
        self._create_compact_info("distance", "📏 Dist", "N/A", 3, 0)
        self._create_compact_info("throttle", "🚀 Thr", "N/A", 3, 1)
        self._create_compact_info("imu_accel", "📊 Accel", "N/A", 4, 0)
        self._create_compact_info("imu_gyro", "🔄 Gyro", "N/A", 4, 1)
        self._create_compact_info("imu_yaw", "🧭 IMU Yaw", "N/A", 5, 0)
        self._create_compact_info("imu_pitch", "📐 Pitch", "N/A", 5, 1)
    
    def _create_compact_info(self, key, label, default_value, row, col):
        """Create a compact info row in grid layout with larger text."""
        frame = tk.Frame(self.content, bg="#252525", height=32)
        frame.grid(row=row, column=col, sticky="ew", padx=2, pady=1)
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=2)
        
        tk.Label(frame, text=label, bg="#252525", fg="#aaaaaa", 
                font=("Segoe UI", 10), anchor="w").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        
        value_label = tk.Label(frame, text=default_value, bg="#252525", fg="#00d4aa", 
                              font=("Segoe UI", 11, "bold"), anchor="e")
        value_label.grid(row=0, column=1, sticky="e", padx=6, pady=4)
        
        self.info_labels[key] = value_label
    
    def _on_robot_changed(self, event):
        """Handle robot selection change."""
        self.selected_robot = self.robot_selector.get()
    
    def update_robot_list(self, robots):
        """Update available robots in dropdown."""
        current_values = list(robots.keys())
        self.robot_selector['values'] = current_values
        if self.selected_robot not in current_values and current_values:
            self.selected_robot = current_values[min(self.panel_id - 1, len(current_values) - 1)]
            self.robot_selector.set(self.selected_robot)
        elif self.selected_robot:
            self.robot_selector.set(self.selected_robot)
    
    def update_info(self, position, battery, robot_type, is_following, follower_state, imu):
        """Update panel information."""
        if position:
            x, y, yaw = position
            self.info_labels["position"].config(text=f"{x:.2f}, {y:.2f}m")
            self.info_labels["orientation"].config(text=f"{yaw*57.3:.0f}°")
        
        if battery:
            pct = battery.get('percentage')
            if pct is not None:
                color = "#00ff88" if pct >= 50 else "#ffaa00" if pct >= 20 else "#ff4444"
                charging = "⚡" if battery.get('charging') else ""
                self.info_labels["battery"].config(text=f"{pct:.0f}%{charging}", fg=color)
            
            voltage = battery.get('voltage')
            if voltage is not None:
                self.info_labels["voltage"].config(text=f"{voltage:.2f}V")
        
        status = "Following" if is_following else "Idle"
        status_color = "#00d4aa" if is_following else "#888888"
        self.info_labels["status"].config(text=status, fg=status_color)
        
        if follower_state:
            wp_idx = follower_state.get('waypoint_index', 0)
            wp_total = follower_state.get('total_waypoints', 0)
            self.info_labels["waypoint"].config(text=f"{wp_idx+1}/{wp_total}")
            
            dist = follower_state.get('distance_to_target')
            self.info_labels["distance"].config(text=f"{dist:.2f}m" if dist else "N/A")
            
            thr = follower_state.get('throttle')
            self.info_labels["throttle"].config(text=f"{thr:.2f}" if thr else "N/A")
        else:
            self.info_labels["waypoint"].config(text="N/A")
            self.info_labels["distance"].config(text="N/A")
            self.info_labels["throttle"].config(text="N/A")
        
        if imu:
            accel = imu.get('linear_accel')
            if accel:
                accel_mag = (accel[0]**2 + accel[1]**2 + accel[2]**2)**0.5
                self.info_labels["imu_accel"].config(text=f"{accel_mag:.2f}m/s²")
            else:
                self.info_labels["imu_accel"].config(text="N/A")
            
            gyro = imu.get('angular_velocity')
            if gyro:
                gyro_mag = (gyro[0]**2 + gyro[1]**2 + gyro[2]**2)**0.5
                self.info_labels["imu_gyro"].config(text=f"{gyro_mag:.2f}rad/s")
            else:
                self.info_labels["imu_gyro"].config(text="N/A")
            
            orientation = imu.get('orientation')
            if orientation:
                x, y, z, w = orientation
                siny_cosp = 2.0 * (w * z + x * y)
                cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
                yaw = math.atan2(siny_cosp, cosy_cosp)
                yaw_deg = math.degrees(yaw)
                
                sinp = 2.0 * (w * y - z * x)
                if abs(sinp) >= 1:
                    pitch = math.copysign(math.pi / 2, sinp)
                else:
                    pitch = math.asin(sinp)
                pitch_deg = math.degrees(pitch)
                
                self.info_labels["imu_yaw"].config(text=f"{yaw_deg:.1f}°")
                self.info_labels["imu_pitch"].config(text=f"{pitch_deg:.1f}°")
            else:
                self.info_labels["imu_yaw"].config(text="N/A")
                self.info_labels["imu_pitch"].config(text="N/A")
        else:
            self.info_labels["imu_accel"].config(text="N/A")
            self.info_labels["imu_gyro"].config(text="N/A")
            self.info_labels["imu_yaw"].config(text="N/A")
            self.info_labels["imu_pitch"].config(text="N/A")


class MonitoringTab:
    """Monitoring tab for status and debug information."""
    
    def __init__(self, parent, state, on_robot_select=None):
        self.frame = parent
        self.state = state
        self.on_robot_select = on_robot_select
        self.panels = []
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup monitoring tab UI."""
        # Configure grid for responsive layout
        for i in range(2):
            self.frame.grid_rowconfigure(i, weight=1)
            self.frame.grid_columnconfigure(i, weight=1)
        
        # Create 4 monitoring panels in 2x2 grid - smaller panels
        for i in range(4):
            panel = RobotMonitorPanel(self.frame, i + 1)
            row = i // 2
            col = i % 2
            panel.frame.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
            self.panels.append(panel)
        
    def update_panels(self, robots, robot_states, follower_states):
        """Update all monitoring panels."""
        # Update robot lists in all panels
        for panel in self.panels:
            panel.update_robot_list(robots)
        
        # Update each panel with its selected robot's info
        for panel in self.panels:
            if panel.selected_robot and panel.selected_robot in robots:
                position = robot_states.get(panel.selected_robot, {})
                pos_tuple = (position.get('x', 0), position.get('y', 0), position.get('yaw', 0))
                battery = robot_states.get(panel.selected_robot, {}).get('battery')
                imu = robot_states.get(panel.selected_robot, {}).get('imu')
                robot_type = robots[panel.selected_robot].robot_type
                is_following = panel.selected_robot in follower_states
                follower_state = follower_states.get(panel.selected_robot)
                
                panel.update_info(pos_tuple, battery, robot_type, is_following, follower_state, imu)
    
    # Legacy methods for compatibility
    def update_status(self, text: str, color: str):
        """Update connection status (compatibility)."""
        pass
    
    def update_debug(self, text: str):
        """Update debug information (compatibility)."""
        pass

