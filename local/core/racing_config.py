"""Racing configuration for multi-robot racing."""

class RacingConfig:
    """Per-robot racing configuration."""
    
    def __init__(self, robot_name: str):
        self.robot_name = robot_name
        self.lateral_offset = 0.0
        self.speed_multiplier = 1.0
        self.loop_path = False
    
    def set_offset(self, offset: float):
        """Set lateral offset in meters (negative=left, positive=right)."""
        self.lateral_offset = max(-1.0, min(1.0, offset))
    
    def set_speed_multiplier(self, multiplier: float):
        """Set speed multiplier (0.1 to 2.0)."""
        self.speed_multiplier = max(0.1, min(2.0, multiplier))
    
    def set_loop(self, loop: bool):
        """Enable/disable path looping."""
        self.loop_path = loop

