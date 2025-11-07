#!/usr/bin/env python3
"""Battery state tracker for robots."""

from __future__ import annotations

from typing import Dict, Optional

try:
    import rospy
    from sensor_msgs.msg import BatteryState
except ImportError as exc:  # pragma: no cover
    rospy = None  # type: ignore
    BatteryState = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from .base_tracker import BaseTracker


class BatteryTracker(BaseTracker):
    """
    Track battery state for robots.
    
    Subscribes to battery topics and updates Robot instances with:
    - Battery voltage
    - Battery percentage
    - Battery current
    - Battery temperature
    - Charging status
    
    Example topic: /robot_name/battery_state
    """
    
    V_FULL = 12.6
    V_EMPTY = 9.0
    
    def __init__(self, queue_size: int = 10):
        """Initialize battery tracker."""
        if _IMPORT_ERROR is not None:
            raise ImportError(
                "rospy and sensor_msgs are required for BatteryTracker"
            ) from _IMPORT_ERROR
        
        super().__init__(queue_size)
    
    def _get_topic_from_config(self, robot_config: Dict) -> Optional[str]:
        """
        Get battery topic from config.
        
        Checks for 'battery_topic' in config, otherwise constructs
        default topic as '/robot_name/battery'.
        
        Args:
            robot_config: Robot configuration dictionary
            
        Returns:
            Battery topic string or None
        """
        # First check if explicitly configured
        battery_topic = robot_config.get("battery_topic")
        if battery_topic:
            return battery_topic
        
        # Construct default topic from robot name
        robot_name = robot_config.get("name")
        if robot_name:
            return f"/{robot_name}/battery"
        
        return None
    
    def _get_message_type(self):
        """Return BatteryState message type."""
        return BatteryState
    
    def _process_message(self, robot_name: str, msg: BatteryState) -> None:
        """
        Process battery state message and update robot.
        
        Args:
            robot_name: Name of the robot
            msg: BatteryState message
        """
        with self._lock:
            robot = self._robots.get(robot_name)
        
        if robot is None:
            return
        
        # Calculate percentage from voltage if not provided
        if msg.percentage <= 0.0 and msg.voltage > 0.0:
            calculated_percentage = max(0.0, min(1.0, (msg.voltage - self.V_EMPTY) / (self.V_FULL - self.V_EMPTY))) * 100.0
        else:
            calculated_percentage = msg.percentage * 100.0 if msg.percentage >= 0 else None
        
        # Update robot battery data
        # BatteryState constants:
        # POWER_SUPPLY_STATUS_UNKNOWN = 0
        # POWER_SUPPLY_STATUS_CHARGING = 1
        # POWER_SUPPLY_STATUS_DISCHARGING = 2
        # POWER_SUPPLY_STATUS_NOT_CHARGING = 3
        # POWER_SUPPLY_STATUS_FULL = 4
        
        robot.update_battery(
            voltage=msg.voltage,
            percentage=calculated_percentage,
            current=msg.current,
            temperature=msg.temperature,
            charging=(msg.power_supply_status == BatteryState.POWER_SUPPLY_STATUS_CHARGING),
            power_supply_status=msg.power_supply_status
        )
        
        # Log significant events
        if calculated_percentage is not None and calculated_percentage < 20.0:
            rospy.logwarn(
                "[BatteryTracker] Low battery for %s: %.1f%% (%.2fV)",
                robot_name, calculated_percentage, msg.voltage
            )

