#!/usr/bin/env python3
"""
Mode Handler
Handles mode switching between click, draw, and record modes.
"""


class ModeHandler:
    """Handles mode switching logic."""
    
    def __init__(self, state, recording_service, update_ui_callback):
        self.state = state
        self.recording_service = recording_service
        self.update_ui = update_ui_callback
    
    def switch_mode(self, mode: str):
        """Switch to a different mode."""
        if self.recording_service.is_recording and mode != self.state.MODE_RECORD:
            self.recording_service.stop_recording()
        
        self.state.current_mode = mode
        self.update_ui(mode)

