#!/usr/bin/env python3
"""Hydra backend server integrating ROS tracking, control and UDP communication."""

from __future__ import annotations

import json
import math
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


try:
    import rospy
except ImportError as exc:  # pragma: no cover - requires ROS environment
    rospy = None  # type: ignore
    _ROS_IMPORT_ERROR = exc
else:
    _ROS_IMPORT_ERROR = None

from ros.ros_controller import ROSController
from ros.ros_tracker import PoseState, ROSTracker
from net.udp_server import UDPServer
from core.config_loader import load_config
from core.robot import Robot, create_robot


DEFAULT_PARAMETERS = {
    "use_prediction": True,
    "estimated_delay_ms": 100,
    "waypoint_tolerance": 0.20,
    "turn_in_place_threshold": 65.0,
    "proportional_gain": 2.8,
    "max_turn_rate": 85.0,
    "slow_down_distance": 0.5,
    "min_speed_ratio": 0.20,
    "curvature_speed_gain": 0.65,
    "look_ahead_distance": 0.4,
    "path_simplification_tolerance": 0.06,
    "min_waypoint_separation": 0.15,
    "segment_pass_distance": 0.09,
    "segment_pass_lateral_factor": 1.7,
    "waypoint_approach_slowdown": 0.30,
    "corner_keep_angle_deg": 22.0,
    "intermediate_corner_slowdown_deg": 90.0,
    "throttle_ramp_rate": 0.9,
}


class BackendServer:
    """Main Hydra backend orchestrator."""

    CONTROL_LOOP_HZ = 20.0

    def __init__(self) -> None:
        if _ROS_IMPORT_ERROR is not None:
            raise ImportError("rospy is required to run the Hydra backend") from _ROS_IMPORT_ERROR

        self.config_loader = load_config()
        hydra_cfg = self.config_loader.get_hydra_config()
        backend_host, backend_port = self.config_loader.get_backend_endpoint()
        self.backend_host = hydra_cfg.get("listen_host", backend_host)
        self.backend_port = backend_port
        self.state_broadcast_hz = int(hydra_cfg.get("state_broadcast_hz", 20))

        self.tracker = ROSTracker()
        self.controller = ROSController(
            default_max_linear=hydra_cfg.get("default_max_linear", 0.5),
            default_max_angular=hydra_cfg.get("default_max_angular", 1.5),
            use_stamped=hydra_cfg.get("use_stamped_cmd", False),
            frame_id=hydra_cfg.get("cmd_frame_id", "base_link"),
        )
        self.udp_server = UDPServer(
            host=self.backend_host,
            port=self.backend_port,
            handler=self._handle_message,
            client_ttl=hydra_cfg.get("client_ttl", 30.0),
        )

        self.parameters = dict(DEFAULT_PARAMETERS)
        self.robots: Dict[str, Robot] = {}

        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._control_thread: Optional[threading.Thread] = None
        self._broadcast_thread: Optional[threading.Thread] = None

        self._register_initial_robots()

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    def start(self) -> None:
        rospy.loginfo("[Backend] Starting UDP server on %s:%s", self.backend_host, self.backend_port)
        self.udp_server.start()

        self._stop_event.clear()
        self._control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self._broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._control_thread.start()
        self._broadcast_thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._control_thread:
            self._control_thread.join(timeout=1.5)
        if self._broadcast_thread:
            self._broadcast_thread.join(timeout=1.5)

        self.udp_server.stop()
        self.controller.shutdown()
        self.tracker.shutdown()

        with self._state_lock:
            for robot in self.robots.values():
                robot.stop_path_following()

    # ------------------------------------------------------------------
    # Robot registration & configuration
    # ------------------------------------------------------------------

    def _register_initial_robots(self) -> None:
        for name, config in self.config_loader.get_robot_config().items():
            try:
                self._add_robot_internal(name, config, persist=False)
            except Exception as exc:  # pragma: no cover - defensive logging
                print(f"[Backend] Failed to register robot {name}: {exc}")

    def _add_robot_internal(self, name: str, config: Dict, persist: bool = True) -> None:
        robot_type = config.get("type", "real")

        robot = create_robot(
            robot_type=robot_type,
            robot_ip=config.get("ip", ""),
            robot_port=config.get("port"),
            username=name,
        )

        # Set ROS controller reference for command sending
        robot.set_ros_controller(self.controller)

        with self._state_lock:
            self.robots[name] = robot

        if robot_type == "real":
            self.tracker.register_robot(name, config)
            self.controller.register_robot(name, config)

        if persist:
            self.config_loader.upsert_robot(name, config)

    def _remove_robot_internal(self, name: str, persist: bool = True) -> None:
        with self._state_lock:
            robot = self.robots.pop(name, None)

        if robot is not None:
            robot.stop_path_following()
        
        self.tracker.remove_robot(name)
        self.controller.remove_robot(name)
        if persist:
            self.config_loader.remove_robot(name)

    # ------------------------------------------------------------------
    # Control loop
    # ------------------------------------------------------------------

    def _control_loop(self) -> None:
        period = 1.0 / self.CONTROL_LOOP_HZ
        last_update = time.time()

        while not self._stop_event.is_set() and not rospy.is_shutdown():
            start = time.time()
            self._refresh_robot_states()

            with self._state_lock:
                robots_snapshot = dict(self.robots)

            for robot_name, robot in robots_snapshot.items():
                if not robot.is_following_path():
                    continue

                robot.update_path_follower_position()
                command = robot.compute_path_command()
                
                if command is None:
                    # Path complete or stopped
                    continue

                throttle, turn_rate = command
                throttle, turn_rate = self._apply_speed_controls(robot_name, robot, throttle, turn_rate)
                robot.send_command(throttle, -turn_rate)

            elapsed = time.time() - start
            sleep_time = max(0.0, period - elapsed)
            time.sleep(sleep_time)

            last_update = time.time()

    def _apply_speed_controls(
        self,
        robot_name: str,
        robot: Robot,
        throttle: float,
        turn_rate: float,
    ) -> Tuple[float, float]:
        params = self.parameters
        follower_state = robot.get_path_follower_state()
        if follower_state is None:
            return throttle, turn_rate
        
        distance_to_waypoint = follower_state.get("distance_to_target") or 999.0

        if throttle > 0.01 and distance_to_waypoint < params["look_ahead_distance"]:
            idx = follower_state.get("waypoint_index", 0)
            if robot.path_follower is not None:
                waypoints = robot.path_follower.waypoints
                if idx + 1 < len(waypoints):
                    x, y, yaw = robot.get_position()
                    next_target = waypoints[idx + 1]
                    dx_next = next_target[0] - x
                    dy_next = next_target[1] - y
                    desired_yaw_next = math.atan2(dy_next, dx_next)

                    angle_diff_next = desired_yaw_next - yaw
                    while angle_diff_next > math.pi:
                        angle_diff_next -= 2 * math.pi
                    while angle_diff_next < -math.pi:
                        angle_diff_next += 2 * math.pi
                    angle_diff_next_deg = math.degrees(angle_diff_next)

                    blend_ratio = 1.0 - (distance_to_waypoint / params["look_ahead_distance"])
                    blend_ratio = max(0.0, min(1.0, blend_ratio))

                    if robot.path_follower is not None:
                        state = robot.path_follower.get_state()
                        angle_diff_current = state.get("angle_to_target")
                        if angle_diff_current is not None:
                            angle_diff_current_deg = math.degrees(angle_diff_current)
                            blended_angle_diff = (
                                (1.0 - blend_ratio) * angle_diff_current_deg
                                + blend_ratio * angle_diff_next_deg
                            )
                            turn_rate = max(
                                -params["max_turn_rate"],
                                min(params["max_turn_rate"], blended_angle_diff * params["proportional_gain"]),
                            )
                            if throttle > 0.0 and params["max_turn_rate"] > 0:
                                curvature_ratio = abs(turn_rate) / params["max_turn_rate"]
                                curvature_scale = 1.0 / (1.0 + params["curvature_speed_gain"] * curvature_ratio)
                                if curvature_scale <= params["min_speed_ratio"]:
                                    throttle = 0.0
                                else:
                                    throttle = min(throttle, max(params["min_speed_ratio"], min(1.0, curvature_scale)))
                            throttle = max(0.0, min(1.0, throttle))

        ramp_rate = params.get("throttle_ramp_rate", 0.0)
        if ramp_rate > 1e-6:
            last_throttle = robot.last_throttle
            max_delta = ramp_rate * (1.0 / self.CONTROL_LOOP_HZ)
            delta = throttle - last_throttle
            if delta > max_delta:
                throttle = last_throttle + max_delta
            elif delta < -max_delta:
                throttle = last_throttle - max_delta

        throttle = max(-1.0, min(1.0, throttle))
        return throttle, turn_rate

    def _refresh_robot_states(self) -> None:
        pose_map: Dict[str, PoseState] = self.tracker.get_all_poses()
        for name, pose in pose_map.items():
            robot = self.robots.get(name)
            if robot:
                robot.update_position(pose.x, pose.y, pose.yaw)

    def _stop_following(self, robot_name: str, reason: str = "stopped") -> None:
        with self._state_lock:
            robot = self.robots.get(robot_name)
        if robot:
            robot.stop_path_following()
        rospy.loginfo("[Backend] Path following stopped for %s (%s)", robot_name, reason)

    # ------------------------------------------------------------------
    # Broadcast loop
    # ------------------------------------------------------------------

    def _broadcast_loop(self) -> None:
        if self.state_broadcast_hz <= 0:
            return

        period = 1.0 / self.state_broadcast_hz
        while not self._stop_event.is_set() and not rospy.is_shutdown():
            start = time.time()
            self._refresh_robot_states()

            with self._state_lock:
                robots_snapshot = dict(self.robots)

            robot_states = {}
            follower_states = {}
            for name, robot in robots_snapshot.items():
                x, y, yaw = robot.get_position()
                robot_states[name] = {
                    "x": x,
                    "y": y,
                    "yaw": yaw,
                    "type": robot.robot_type,
                    "is_following": robot.is_following_path(),
                }
                
                if robot.is_following_path():
                    state = robot.get_path_follower_state()
                    if state:
                        follower_states[name] = state

            self.udp_server.broadcast({"type": "robot_states", "data": robot_states})

            if follower_states:
                self.udp_server.broadcast({"type": "path_following_state", "data": follower_states})

            connection_status = {
                "ros_connected": True,
                "tracked_robots": list(robot_states.keys()),
                "controlled_robots": list(self.controller.get_registered_robots().keys()),
                "connected_clients": len(self.udp_server.get_connected_clients()),
            }
            self.udp_server.broadcast({"type": "connection_status", "data": connection_status})

            elapsed = time.time() - start
            sleep_time = max(0.0, period - elapsed)
            time.sleep(sleep_time)

    # ------------------------------------------------------------------
    # UDP message handling
    # ------------------------------------------------------------------

    def _handle_message(self, message: Dict, addr: Tuple[str, int]) -> None:
        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type is None:
            self._send_error(addr, "Message missing 'type'")
            return

        handler_name = f"_cmd_{msg_type}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            self._send_error(addr, f"Unknown command type '{msg_type}'")
            return

        try:
            handler(data, addr)
        except Exception as exc:  # pragma: no cover - defensive logging
            rospy.logerr("[Backend] Command '%s' failed: %s", msg_type, exc)
            self._send_error(addr, f"Command '{msg_type}' failed: {exc}")

    def _send_ack(self, addr: Tuple[str, int], command: str, payload: Optional[Dict] = None) -> None:
        reply = {"type": "ack", "data": {"command": command, "status": "ok"}}
        if payload:
            reply["data"].update(payload)
        self.udp_server.send_to(addr, reply)

    def _send_error(self, addr: Tuple[str, int], message: str) -> None:
        self.udp_server.send_to(addr, {"type": "error", "data": {"message": message}})

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _cmd_add_robot(self, data: Dict, addr: Tuple[str, int]) -> None:
        name = data.get("name")
        if not name:
            raise ValueError("'name' is required")

        robot_type = data.get("type", "real")
        robot_config = {
            "name": name,
            "type": robot_type,
        }
        if "umh_id" in data and data.get("umh_id") is not None:
            robot_config["umh_id"] = data.get("umh_id")
        if "cmd_vel_topic" in data and data.get("cmd_vel_topic") is not None:
            robot_config["cmd_vel_topic"] = data.get("cmd_vel_topic")
        if isinstance(data.get("max_linear"), (int, float)):
            robot_config["max_linear"] = float(data.get("max_linear"))
        if isinstance(data.get("max_angular"), (int, float)):
            robot_config["max_angular"] = float(data.get("max_angular"))

        self._add_robot_internal(name, robot_config, persist=True)
        self._send_ack(addr, "add_robot")

    def _cmd_remove_robot(self, data: Dict, addr: Tuple[str, int]) -> None:
        name = data.get("name")
        if not name:
            raise ValueError("'name' is required")
        self._remove_robot_internal(name)
        self._send_ack(addr, "remove_robot")

    def _cmd_set_path(self, data: Dict, addr: Tuple[str, int]) -> None:
        name = data.get("robot")
        waypoints = data.get("waypoints", [])
        if not name or not isinstance(waypoints, list):
            raise ValueError("'robot' and 'waypoints' are required")

        with self._state_lock:
            robot = self.robots.get(name)
            if not robot:
                raise ValueError(f"Robot '{name}' not registered")
            robot.set_path(waypoints)
        self._send_ack(addr, "set_path", {"num_waypoints": len(waypoints)})

    def _cmd_clear_path(self, data: Dict, addr: Tuple[str, int]) -> None:
        name = data.get("robot")
        if not name:
            raise ValueError("'robot' is required")
        with self._state_lock:
            robot = self.robots.get(name)
            if robot:
                robot.clear_path()
        self._send_ack(addr, "clear_path")

    def _cmd_start_path(self, data: Dict, addr: Tuple[str, int]) -> None:
        name = data.get("robot")
        if not name:
            raise ValueError("'robot' is required")
        self._start_path_for_robot(name)
        self._send_ack(addr, "start_path")

    def _cmd_start_all_paths(self, data: Dict, addr: Tuple[str, int]) -> None:
        started = 0
        with self._state_lock:
            robots_snapshot = dict(self.robots)
        for name, robot in robots_snapshot.items():
            if robot.path_data and robot.path_data.waypoints:
                if self._start_path_for_robot(name):
                    started += 1
        self._send_ack(addr, "start_all_paths", {"started": started})

    def _cmd_stop_path(self, data: Dict, addr: Tuple[str, int]) -> None:
        name = data.get("robot")
        if not name:
            raise ValueError("'robot' is required")
        self._stop_following(name, reason="commanded stop")
        self._send_ack(addr, "stop_path")

    def _cmd_stop_all(self, data: Dict, addr: Tuple[str, int]) -> None:
        for name in list(self.robots.keys()):
            self._stop_following(name, reason="global stop")
        self._send_ack(addr, "stop_all")

    def _cmd_emergency_stop(self, data: Dict, addr: Tuple[str, int]) -> None:
        self._cmd_stop_all(data, addr)
        self._send_ack(addr, "emergency_stop")

    def _cmd_set_racing_config(self, data: Dict, addr: Tuple[str, int]) -> None:
        name = data.get("robot")
        if not name:
            raise ValueError("'robot' is required")
        
        with self._state_lock:
            robot = self.robots.get(name)
            if not robot:
                raise ValueError(f"Robot '{name}' not registered")

        offset = data.get("offset")
        speed = data.get("speed")
        loop = data.get("loop")
        
        robot.update_racing_config(
            offset=float(offset) if offset is not None else None,
            speed=float(speed) if speed is not None else None,
            loop=bool(loop) if loop is not None else None,
        )

        self._send_ack(addr, "set_racing_config")

    def _cmd_set_parameters(self, data: Dict, addr: Tuple[str, int]) -> None:
        updated = {}
        for key, value in data.items():
            if key in self.parameters:
                if isinstance(value, bool):
                    self.parameters[key] = value
                elif isinstance(value, (int, float)):
                    self.parameters[key] = float(value)
                else:
                    self.parameters[key] = value
                updated[key] = self.parameters[key]
        if updated:
            with self._state_lock:
                for robot in self.robots.values():
                    if robot.path_follower is not None:
                        robot.path_follower.use_prediction = bool(self.parameters["use_prediction"])
                        robot.path_follower.estimated_delay_ms = float(self.parameters["estimated_delay_ms"])
        self._send_ack(addr, "set_parameters", {"updated": updated})

    def _cmd_manual_control(self, data: Dict, addr: Tuple[str, int]) -> None:
        name = data.get("robot")
        throttle = data.get("throttle", 0.0)
        turn_rate = data.get("turn_rate", 0.0)
        if not name:
            raise ValueError("'robot' is required")

        with self._state_lock:
            robot = self.robots.get(name)
            if not robot:
                raise ValueError(f"Robot '{name}' not registered")
            robot.stop_path_following()

        robot.send_command(float(throttle), float(turn_rate))
        self._send_ack(addr, "manual_control")

    def _cmd_get_diagnostics(self, data: Dict, addr: Tuple[str, int]) -> None:
        """Get diagnostic information about tracking and robot states."""
        poses = self.tracker.get_all_poses()
        diagnostics = {
            "tracked_poses": {},
            "robot_states": {},
            "ros_connected": not rospy.is_shutdown(),
        }
        
        for name, pose in poses.items():
            diagnostics["tracked_poses"][name] = {
                "x": pose.x,
                "y": pose.y,
                "z": pose.z,
                "yaw": pose.yaw,
                "timestamp": pose.timestamp,
                "frame_id": pose.frame_id,
            }
        
        for name, robot in self.robots.items():
            x, y, yaw = robot.get_position()
            diagnostics["robot_states"][name] = {
                "x": x,
                "y": y,
                "yaw": yaw,
                "type": robot.robot_type,
            }
        
        self._send_ack(addr, "get_diagnostics", diagnostics)

    def _cmd_ping(self, data: Dict, addr: Tuple[str, int]) -> None:
        """Handle ping/heartbeat messages from clients to keep connection alive."""
        # No action needed - just receiving the message updates the client timestamp
        pass

    def _cmd_hello(self, data: Dict, addr: Tuple[str, int]) -> None:
        """Handle hello messages from clients."""
        # No action needed - just receiving the message registers the client
        pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _start_path_for_robot(self, name: str) -> bool:
        with self._state_lock:
            robot = self.robots.get(name)
            if not robot:
                return False
        
        if robot.is_following_path():
            return False
        
        if not robot.path_data or not robot.path_data.waypoints:
            return False

        params = self.parameters
        path_follower_params = {
            "waypoint_tolerance": params["waypoint_tolerance"],
            "turn_in_place_threshold": params["turn_in_place_threshold"],
            "proportional_gain": params["proportional_gain"],
            "max_turn_rate": params["max_turn_rate"],
            "use_prediction": params["use_prediction"],
            "estimated_delay_ms": params["estimated_delay_ms"],
            "curvature_speed_gain": params["curvature_speed_gain"],
            "min_speed_ratio": params["min_speed_ratio"],
            "slow_down_distance": params["slow_down_distance"],
            "path_simplification_tolerance": params["path_simplification_tolerance"],
            "min_waypoint_separation": params["min_waypoint_separation"],
            "segment_pass_distance": params["segment_pass_distance"],
            "segment_pass_lateral_factor": params["segment_pass_lateral_factor"],
            "waypoint_approach_slowdown": params["waypoint_approach_slowdown"],
            "corner_keep_angle_deg": params["corner_keep_angle_deg"],
            "intermediate_corner_slowdown_deg": params["intermediate_corner_slowdown_deg"],
        }
        
        if robot.start_path_following(path_follower_params):
            rospy.loginfo("[Backend] Started path follower for %s (%d waypoints)", name, len(robot.path_data.waypoints))
            return True
        return False


def main() -> None:
    rospy.init_node("hydra_backend", anonymous=False)
    server = BackendServer()
    server.start()
    rospy.loginfo("[Backend] Hydra backend running")

    try:
        rospy.spin()
    except KeyboardInterrupt:
        rospy.loginfo("[Backend] Interrupted, shutting down...")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()

