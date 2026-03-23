from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import rclpy
from geometry_msgs.msg import Pose2D, Twist, TwistStamped
from hydra_common import RacingConfig, load_fleet_config
from hydra_interfaces.action import FollowPath
from hydra_interfaces.msg import PathProgress, RobotStatus
from hydra_interfaces.srv import SetMode, SetRacingConfig
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import Header
from std_srvs.srv import Trigger

from .udp_broadcaster import UDPBroadcaster
from .udp_server import UDPServer


@dataclass
class RobotBridgeState:
    robot_type: str
    color: str
    client_port: int
    status: Optional[RobotStatus] = None
    progress: Optional[PathProgress] = None
    last_status_monotonic: float = 0.0
    pending_waypoints: list[Tuple[float, float]] = field(default_factory=list)
    racing_config: RacingConfig = field(default_factory=lambda: RacingConfig("robot"))
    teleop_active: bool = False


class HydraSupervisorBridge(Node):
    def __init__(self) -> None:
        super().__init__("hydra_supervisor_bridge")
        self.declare_parameter("config_path", "")
        cfg_path = self.get_parameter("config_path").get_parameter_value().string_value or None
        self.fleet = load_fleet_config(cfg_path)
        hydra_cfg = self.fleet.hydra_config
        self.supervisor_host = str(hydra_cfg.get("supervisor_host", "127.0.0.1"))
        self.supervisor_port = int(hydra_cfg.get("supervisor_port", 9998))
        self.broadcast_hz = float(hydra_cfg.get("state_broadcast_hz", 20))
        self.heartbeat_hz = float(hydra_cfg.get("supervisor_heartbeat_hz", 2.0))
        self.status_timeout = max(2.0, 2.5 / max(self.heartbeat_hz, 0.1))

        self.state_lock = threading.Lock()
        self.robots: Dict[str, RobotBridgeState] = {}
        self.follow_actions: Dict[str, ActionClient] = {}
        self.mode_clients = {}
        self.racing_clients = {}
        self.estop_clients = {}
        self.cancel_clients = {}
        self.clear_clients = {}
        self.teleop_publishers = {}
        self.teleop_stamped = {}
        self.udp_server = UDPServer(self.supervisor_host, self.supervisor_port, self._handle_udp_message, client_ttl=30.0)
        self.udp_broadcaster = UDPBroadcaster(self.fleet.gamma_client_ips()) if self.fleet.gamma_client_ips() else None
        self.heartbeat_pub = self.create_publisher(Header, "/hydra/supervisor_heartbeat", 10)

        for name, robot in self.fleet.robots.items():
            bridge_state = RobotBridgeState(robot.robot_type, robot.color, robot.client_port, racing_config=RacingConfig(name))
            self.robots[name] = bridge_state
            self.create_subscription(RobotStatus, f"{robot.namespace}/hydra/status", lambda msg, robot_name=name: self._on_status(robot_name, msg), 10)
            self.create_subscription(PathProgress, f"{robot.namespace}/hydra/path_progress", lambda msg, robot_name=name: self._on_progress(robot_name, msg), 10)
            self.follow_actions[name] = ActionClient(self, FollowPath, f"{robot.namespace}/hydra/follow_path")
            self.mode_clients[name] = self.create_client(SetMode, f"{robot.namespace}/hydra/set_mode")
            self.racing_clients[name] = self.create_client(SetRacingConfig, f"{robot.namespace}/hydra/set_racing_config")
            self.estop_clients[name] = self.create_client(Trigger, f"{robot.namespace}/hydra/emergency_stop")
            self.cancel_clients[name] = self.create_client(Trigger, f"{robot.namespace}/hydra/cancel_motion")
            self.clear_clients[name] = self.create_client(Trigger, f"{robot.namespace}/hydra/clear_path")
            use_stamped = robot.uses_stamped_cmd_vel()
            self.teleop_stamped[name] = use_stamped
            self.teleop_publishers[name] = self.create_publisher(
                TwistStamped if use_stamped else Twist,
                robot.cmd_vel_topic,
                10,
            )

        self.udp_server.start()
        self.create_timer(1.0 / self.broadcast_hz, self._broadcast_tick)
        self.create_timer(1.0 / self.heartbeat_hz, self._heartbeat_tick)
        self.get_logger().info(f"Supervisor bridge listening on {self.supervisor_host}:{self.supervisor_port}")

    def destroy_node(self):
        self.udp_server.stop()
        if self.udp_broadcaster:
            self.udp_broadcaster.close()
        super().destroy_node()

    def _on_status(self, robot_name: str, msg: RobotStatus) -> None:
        with self.state_lock:
            state = self.robots[robot_name]
            state.status = msg
            state.last_status_monotonic = time.monotonic()

    def _on_progress(self, robot_name: str, msg: PathProgress) -> None:
        with self.state_lock:
            self.robots[robot_name].progress = msg

    def _heartbeat_tick(self) -> None:
        header = Header()
        header.stamp = self.get_clock().now().to_msg()
        self.heartbeat_pub.publish(header)

    def _broadcast_tick(self) -> None:
        now = time.monotonic()
        robot_states = {}
        follower_states = {}
        controlled_robots = []
        with self.state_lock:
            for name, state in self.robots.items():
                status = state.status
                progress = state.progress
                if status and now - state.last_status_monotonic <= self.status_timeout:
                    controlled_robots.append(name)
                    robot_states[name] = {
                        "x": float(status.x),
                        "y": float(status.y),
                        "yaw": float(status.yaw),
                        "type": status.robot_type or state.robot_type,
                        "is_following": bool(status.path_active),
                        "battery": {
                            "voltage": float(status.battery_voltage),
                            "percentage": float(status.battery_percentage),
                        } if status.battery_voltage == status.battery_voltage else None,
                        "imu": {
                            "orientation": [0.0, 0.0, float(status.imu_yaw)],
                        } if status.imu_yaw == status.imu_yaw else None,
                        "ranges": {
                            "values": {
                                "fl": float(status.range_fl),
                                "fr": float(status.range_fr),
                                "rl": float(status.range_rl),
                                "rr": float(status.range_rr),
                            }
                        },
                    }
                    if progress and progress.active:
                        follower_states[name] = {
                            "distance_to_target": float(progress.distance_to_target),
                            "waypoint_index": int(progress.waypoint_index),
                            "total_waypoints": int(progress.total_waypoints),
                            "throttle": float(progress.throttle),
                            "completion_reason": progress.completion_reason,
                        }
                    if self.udp_broadcaster and state.client_port > 0:
                        flattened = [
                            name,
                            float(status.x),
                            float(status.y),
                            float(status.yaw),
                            status.robot_type or state.robot_type,
                            bool(status.path_active),
                            float(status.battery_percentage) if status.battery_percentage == status.battery_percentage else None,
                            float(status.imu_yaw) if status.imu_yaw == status.imu_yaw else None,
                            float(status.range_fl) if status.range_fl == status.range_fl else None,
                            float(status.range_fr) if status.range_fr == status.range_fr else None,
                            float(status.range_rl) if status.range_rl == status.range_rl else None,
                            float(status.range_rr) if status.range_rr == status.range_rr else None,
                            bool(status.path_active),
                        ]
                        self.udp_broadcaster.send_robot_state(state.client_port, flattened)
                else:
                    robot_states[name] = {
                        "x": 0.0,
                        "y": 0.0,
                        "yaw": 0.0,
                        "type": state.robot_type,
                        "is_following": False,
                        "battery": None,
                        "imu": None,
                        "ranges": {"values": {}},
                    }

        self.udp_server.broadcast({"type": "robot_states", "data": robot_states})
        if follower_states:
            self.udp_server.broadcast({"type": "path_following_state", "data": follower_states})
        connection_status = {
            "ros_connected": True,
            "tracked_robots": list(robot_states.keys()),
            "controlled_robots": controlled_robots,
            "connected_clients": len(self.udp_server.get_connected_clients()),
        }
        self.udp_server.broadcast({"type": "connection_status", "data": connection_status})

    def _send_ack(self, addr, command: str, payload: Optional[dict] = None) -> None:
        data = {"type": "ack", "data": {"command": command, "status": "ok"}}
        if payload:
            data["data"].update(payload)
        self.udp_server.send_to(addr, data)

    def _send_error(self, addr, message: str) -> None:
        self.udp_server.send_to(addr, {"type": "error", "data": {"message": message}})

    def _handle_udp_message(self, message: dict, addr) -> None:
        msg_type = message.get("type")
        data = message.get("data", {})
        handler = getattr(self, f"_cmd_{msg_type}", None)
        if handler is None:
            self._send_error(addr, f"Unknown command type '{msg_type}'")
            return
        try:
            handler(data, addr)
        except Exception as exc:
            self.get_logger().error(f"UDP command {msg_type} failed: {exc}")
            self._send_error(addr, str(exc))

    def _cmd_hello(self, _data, _addr) -> None:
        pass

    def _cmd_ping(self, _data, _addr) -> None:
        pass

    def _cmd_set_path(self, data, addr) -> None:
        name = data.get("robot")
        waypoints = data.get("waypoints", [])
        if not name or not isinstance(waypoints, list):
            raise ValueError("'robot' and 'waypoints' are required")
        with self.state_lock:
            self.robots[name].pending_waypoints = [(float(x), float(y)) for x, y in waypoints]
        self._send_ack(addr, "set_path", {"num_waypoints": len(waypoints)})

    def _cmd_clear_path(self, data, addr) -> None:
        name = data.get("robot")
        if not name:
            raise ValueError("'robot' is required")
        with self.state_lock:
            self.robots[name].pending_waypoints = []
        self._call_trigger(self.clear_clients[name])
        self._send_ack(addr, "clear_path")

    def _cmd_set_racing_config(self, data, addr) -> None:
        name = data.get("robot")
        if not name:
            raise ValueError("'robot' is required")
        req = SetRacingConfig.Request()
        req.lateral_offset = float(data.get("offset", 0.0))
        req.speed_multiplier = float(data.get("speed", 1.0))
        req.loop_path = bool(data.get("loop", False))
        with self.state_lock:
            cfg = self.robots[name].racing_config
            cfg.set_offset(req.lateral_offset)
            cfg.set_speed_multiplier(req.speed_multiplier)
            cfg.set_loop(req.loop_path)
        self._call_service(self.racing_clients[name], req)
        self._send_ack(addr, "set_racing_config")

    def _cmd_start_path(self, data, addr) -> None:
        name = data.get("robot")
        if not name:
            raise ValueError("'robot' is required")
        self._submit_path_goal(name)
        self._send_ack(addr, "start_path")

    def _cmd_start_all_paths(self, _data, addr) -> None:
        started = 0
        with self.state_lock:
            robot_names = list(self.robots.keys())
        for name in robot_names:
            if self._submit_path_goal(name):
                started += 1
        self._send_ack(addr, "start_all_paths", {"started": started})

    def _cmd_stop_path(self, data, addr) -> None:
        name = data.get("robot")
        if not name:
            raise ValueError("'robot' is required")
        self._call_trigger(self.cancel_clients[name])
        self._send_ack(addr, "stop_path")

    def _cmd_stop_all(self, _data, addr) -> None:
        for client in self.cancel_clients.values():
            self._call_trigger(client)
        self._send_ack(addr, "stop_all")

    def _cmd_emergency_stop(self, _data, addr) -> None:
        for client in self.estop_clients.values():
            self._call_trigger(client)
        self._send_ack(addr, "emergency_stop")

    def _cmd_manual_control(self, data, addr) -> None:
        name = data.get("robot")
        if not name:
            raise ValueError("'robot' is required")
        throttle = float(data.get("throttle", 0.0))
        turn_rate = float(data.get("turn_rate", 0.0))
        req = SetMode.Request()
        req.mode = "MANUAL" if abs(throttle) > 1e-3 or abs(turn_rate) > 1e-3 else "IDLE"
        self._call_service(self.mode_clients[name], req)
        twist = Twist()
        robot = self.fleet.get_robot(name)
        max_linear = robot.max_linear if robot else 0.5
        max_angular = robot.max_angular if robot else 1.5
        twist.linear.x = max(-max_linear, min(max_linear, throttle * max_linear))
        twist.angular.z = max(-max_angular, min(max_angular, turn_rate * 3.141592653589793 / 180.0))
        self._publish_teleop_twist(name, twist)
        self._send_ack(addr, "manual_control")

    def _publish_teleop_twist(self, robot_name: str, twist: Twist) -> None:
        pub = self.teleop_publishers[robot_name]
        if self.teleop_stamped.get(robot_name, False):
            stamped = TwistStamped()
            stamped.header.stamp = self.get_clock().now().to_msg()
            stamped.twist = twist
            pub.publish(stamped)
            return
        pub.publish(twist)

    def _cmd_set_parameters(self, _data, addr) -> None:
        self._send_ack(addr, "set_parameters", {"updated": {}})

    def _cmd_add_robot(self, _data, addr) -> None:
        self._send_error(addr, "Runtime add_robot is not supported in the ROS 2 bridge; update config/fleet.json instead")

    def _cmd_remove_robot(self, _data, addr) -> None:
        self._send_error(addr, "Runtime remove_robot is not supported in the ROS 2 bridge; update config/fleet.json instead")

    def _cmd_get_diagnostics(self, _data, addr) -> None:
        diagnostics = {}
        with self.state_lock:
            for name, state in self.robots.items():
                diagnostics[name] = {
                    "status_seen": state.status is not None,
                    "path_seen": state.progress is not None,
                    "pending_waypoints": len(state.pending_waypoints),
                }
        self._send_ack(addr, "get_diagnostics", {"robots": diagnostics})

    def _submit_path_goal(self, name: str) -> bool:
        with self.state_lock:
            state = self.robots[name]
            pending = list(state.pending_waypoints)
            cfg = state.racing_config
        if not pending:
            return False
        client = self.follow_actions[name]
        if not client.wait_for_server(timeout_sec=1.0):
            self.get_logger().warning(f"follow_path action not available for {name}")
            return False
        req = FollowPath.Goal()
        req.loop = bool(cfg.loop_path)
        req.speed_multiplier = float(cfg.speed_multiplier)
        req.lateral_offset = float(cfg.lateral_offset)
        req.waypoints = [Pose2D(x=float(x), y=float(y), theta=0.0) for x, y in pending]
        client.send_goal_async(req)
        return True

    def _call_trigger(self, client) -> None:
        if client.wait_for_service(timeout_sec=0.2):
            client.call_async(Trigger.Request())

    def _call_service(self, client, request) -> None:
        if client.wait_for_service(timeout_sec=0.2):
            client.call_async(request)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = HydraSupervisorBridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
