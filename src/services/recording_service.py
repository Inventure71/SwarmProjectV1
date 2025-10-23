#!/usr/bin/env python3
"""
Motion Recording Service
Handles recording robot motion via joystick control.
"""

import math
import time
from typing import List, Tuple, Optional, Callable


class RecordingService:
    """Service for recording robot motion via joystick control."""
    
    def __init__(self, robot_controller, robot_tracker, robot, canvas, world_to_canvas_func):
        self.robot_controller = robot_controller
        self.robot_tracker = robot_tracker
        self.robot = robot
        self.canvas = canvas
        self.world_to_canvas = world_to_canvas_func
        
        # Recording state
        self.is_recording = False
        self.recorded_positions: List[Tuple[float, float]] = []
        self.last_recorded_position: Optional[Tuple[float, float]] = None
        self.record_sample_distance = 0.05  # meters between sampled points
        
        # Control state
        self.joystick_control_active = False
        self.max_turn_rate = 70.0  # degrees per second
        
        # Callbacks
        self.on_recording_start: Optional[Callable] = None
        self.on_recording_stop: Optional[Callable] = None
        self.on_position_recorded: Optional[Callable] = None
    
    def start_recording(self):
        """Start recording robot motion."""
        if not self.robot_controller.connected or self.robot is None:
            return False
        
        self.is_recording = True
        self.recorded_positions = []
        self.last_recorded_position = None
        
        if self.on_recording_start:
            self.on_recording_start()
        
        return True
    
    def stop_recording(self):
        """Stop recording and return recorded positions."""
        self.is_recording = False
        
        # Stop robot
        if self.robot_controller.connected:
            self.robot_controller.send_command(0.0, 0.0)
        
        if self.on_recording_stop:
            self.on_recording_stop()
        
        return self.recorded_positions.copy()
    
    def process_joystick_input(self, joy_x: float, joy_y: float):
        """Process joystick input and control robot."""
        if not self.joystick_control_active:
            return
        
        # Convert joystick to robot commands
        # joy_y: forward/backward (-1 to 1)
        # joy_x: left/right turn (-1 to 1)
        
        # Determine throttle (-1..1) based on joystick input
        throttle = joy_y if abs(joy_y) > 0.1 else 0.0
        throttle = max(-1.0, min(1.0, throttle))
        
        # Calculate turn rate (degrees per second)
        turn_rate = joy_x * self.max_turn_rate
        
        # Apply forward/backward speed modulation
        # Send command to robot
        if self.robot_controller.connected:
            self.robot_controller.send_command(throttle, turn_rate)
        
        # Record position if moved enough
        self._record_position_if_needed(joy_x, joy_y)
    
    def _record_position_if_needed(self, joy_x: float, joy_y: float):
        """Record robot position if it has moved enough."""
        if not self.is_recording or self.robot is None:
            return
        
        x, y, yaw = self.robot.get_position()
        
        # Check if we should record this position
        should_record = False
        if self.last_recorded_position is None:
            should_record = True
        else:
            last_x, last_y = self.last_recorded_position
            dist = math.sqrt((x - last_x)**2 + (y - last_y)**2)
            if dist >= self.record_sample_distance:
                should_record = True
        
        if should_record and (abs(joy_x) > 0.05 or abs(joy_y) > 0.05):
            self.recorded_positions.append((x, y))
            self.last_recorded_position = (x, y)
            
            # Draw real-time recording trace
            canvas_x, canvas_y = self.world_to_canvas(x, y)
            size = 2
            self.canvas.create_oval(
                canvas_x - size, canvas_y - size,
                canvas_x + size, canvas_y + size,
                fill='#ff6600', outline='#ff6600', tags='recording_trace'
            )
            
            if self.on_position_recorded:
                self.on_position_recorded(len(self.recorded_positions))
    
    def get_recorded_positions(self) -> List[Tuple[float, float]]:
        """Get list of recorded positions."""
        return self.recorded_positions.copy()
    
    def clear_recorded_positions(self):
        """Clear all recorded positions."""
        self.recorded_positions = []
        self.last_recorded_position = None
        self.canvas.delete('recording_trace')
    
    def set_sample_distance(self, distance: float):
        """Set the minimum distance between recorded points."""
        self.record_sample_distance = distance
    
    def set_max_turn_rate(self, rate: float):
        """Set the maximum turn rate for joystick control."""
        self.max_turn_rate = rate

    def set_joystick_enabled(self, enabled: bool):
        """Enable or disable joystick control."""
        enable_flag = bool(enabled)
        if not enable_flag and self.joystick_control_active and self.robot_controller.connected:
            self.robot_controller.send_command(0.0, 0.0)
        self.joystick_control_active = enable_flag
