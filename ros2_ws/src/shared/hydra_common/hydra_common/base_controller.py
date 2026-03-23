from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Optional

class BaseController(ABC):
    """
    Abstract base class for robot controllers ('Brains').
    """

    @abstractmethod
    def update_state(self, x: float, y: float, yaw: float, timestamp: float = None) -> None:
        """Update the controller with the current robot state."""
        pass

    @abstractmethod
    def compute_command(self) -> Tuple[float, float]:
        """
        Compute the control command.
        Returns:
            (throttle, turn_rate)
            throttle: -1.0 to 1.0
            turn_rate: degrees per second
        """
        pass

    @abstractmethod
    def is_complete(self) -> bool:
        """Check if the task is complete."""
        pass

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Get the internal state for monitoring/debugging."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the controller state."""
        pass

