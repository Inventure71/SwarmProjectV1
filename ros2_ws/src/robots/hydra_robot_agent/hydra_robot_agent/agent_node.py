from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Optional

import rclpy
from builtin_interfaces.msg import Time as TimeMsg
from geometry_msgs.msg import Pose2D, PoseStamped, Twist, TwistStamped
from hydra_common import PathFollower, RacingConfig, load_fleet_config
from hydra_interfaces.action import FollowPath
from hydra_interfaces.msg import PathProgress, RobotDiagnostics, RobotStatus
from hydra_interfaces.srv import SetMode, SetRacingConfig
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from sensor_msgs.msg import BatteryState, Imu, Range
from std_msgs.msg import Header
from std_srvs.srv import Trigger


def _stamp_now(node: Node) -> TimeMsg:
    return node.get_clock().now().to_msg()


def _quat_to_yaw(x: float, y: float, z: float, w: float) -> float:
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return -math.atan2(siny_cosp, cosy_cosp)


@dataclass
class TelemetryState:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    battery_percentage: float = float("nan")
    battery_voltage: float = float("nan")
    imu_yaw: float = float("nan")
    range_fl: float = float("nan")
    range_fr: float = float("nan")
    range_rl: float = float("nan")
    range_rr: float = float("nan")
    last_pose_monotonic: float = 0.0
    last_heartbeat_monotonic: float = 0.0
    fault_reason: str = ""


class HydraRobotAgent(Node):
    MODE_IDLE = "IDLE"
    MODE_MANUAL = "MANUAL"
    MODE_FOLLOW_PATH = "FOLLOW_PATH"
    MODE_ESTOP = "ESTOP"
    MODE_FAULT = "FAULT"

    def __init__(self) -> None:
        super().__init__("hydra_robot_agent")
        self.declare_parameter("robot_name", "")
        self.declare_parameter("config_path", "")

        robot_name = self.get_parameter("robot_name").get_parameter_value().string_value
        config_path = self.get_parameter("config_path").get_parameter_value().string_value or None
        if not robot_name:
            raise ValueError("robot_name parameter is required")

        fleet = load_fleet_config(config_path)
        robot = fleet.get_robot(robot_name)
        if robot is None:
            raise ValueError(f"Robot '{robot_name}' not found in fleet config")
        self.robot = robot
        self.hydra_cfg = fleet.hydra_config
        self.cb_group = ReentrantCallbackGroup()
        self.pose_flip_x = self.robot.should_flip_pose_x()

        self.telemetry = TelemetryState()
        self.mode = self.MODE_IDLE
        self.active_control_source = "none"
        self.estopped = False
        self.follower: Optional[PathFollower] = None
        self.racing_config = RacingConfig(robot_name)
        self._path_lock = threading.Lock()
        self._goal_handle = None
        self._goal_done = threading.Event()
        self._completion_reason = ""
        self._path_progress = PathProgress(robot_name=robot_name)

        self.pose_timeout = float(self.hydra_cfg.get("pose_stale_timeout_sec", 0.5))
        self.heartbeat_timeout = float(self.hydra_cfg.get("supervisor_heartbeat_timeout_sec", 1.0))
        self.control_hz = float(self.hydra_cfg.get("path_control_hz", 20.0))
        self.status_hz = float(self.hydra_cfg.get("status_publish_hz", 10.0))

        self.cmd_pub = self.create_publisher(
            TwistStamped if self.robot.uses_stamped_cmd_vel() else Twist,
            self.robot.cmd_vel_topic,
            10,
        )
        self.status_pub = self.create_publisher(RobotStatus, f"{self.robot.namespace}/hydra/status", 10)
        self.progress_pub = self.create_publisher(PathProgress, f"{self.robot.namespace}/hydra/path_progress", 10)
        self.pose_pub = self.create_publisher(PoseStamped, f"{self.robot.namespace}/hydra/pose", 10)
        self.diag_pub = self.create_publisher(RobotDiagnostics, f"{self.robot.namespace}/hydra/diagnostics", 10)

        self.create_subscription(Header, "/hydra/supervisor_heartbeat", self._on_heartbeat, 10)
        pose_topic = self.robot.resolved_pose_topic()
        if pose_topic:
            self.create_subscription(PoseStamped, pose_topic, self._on_pose, 10)
        if self.robot.battery_topic:
            self.create_subscription(BatteryState, self.robot.battery_topic, self._on_battery, 10)
        if self.robot.imu_topic:
            self.create_subscription(Imu, self.robot.imu_topic, self._on_imu, 10)
        for sensor, topic in self.robot.range_topics.items():
            self.create_subscription(Range, topic, lambda msg, sensor_name=sensor: self._on_range(sensor_name, msg), 10)

        self.mode_srv = self.create_service(SetMode, f"{self.robot.namespace}/hydra/set_mode", self._handle_set_mode, callback_group=self.cb_group)
        self.racing_srv = self.create_service(SetRacingConfig, f"{self.robot.namespace}/hydra/set_racing_config", self._handle_set_racing, callback_group=self.cb_group)
        self.estop_srv = self.create_service(Trigger, f"{self.robot.namespace}/hydra/emergency_stop", self._handle_estop, callback_group=self.cb_group)
        self.cancel_srv = self.create_service(Trigger, f"{self.robot.namespace}/hydra/cancel_motion", self._handle_cancel, callback_group=self.cb_group)
        self.clear_srv = self.create_service(Trigger, f"{self.robot.namespace}/hydra/clear_path", self._handle_clear, callback_group=self.cb_group)
        self.action_server = ActionServer(
            self,
            FollowPath,
            f"{self.robot.namespace}/hydra/follow_path",
            execute_callback=self._execute_follow_path,
            goal_callback=self._goal_callback,
            cancel_callback=self._cancel_callback,
            callback_group=self.cb_group,
        )

        self.create_timer(1.0 / self.control_hz, self._control_tick, callback_group=self.cb_group)
        self.create_timer(1.0 / self.status_hz, self._status_tick, callback_group=self.cb_group)

        self.get_logger().info(f"Hydra robot agent ready for {self.robot.name}")
        if self.pose_flip_x:
            self.get_logger().info("Pose X-axis mirroring enabled for this robot")

    def _goal_callback(self, goal_request: FollowPath.Goal):
        if self.mode in {self.MODE_ESTOP, self.MODE_FAULT, self.MODE_MANUAL}:
            return GoalResponse.REJECT
        if not goal_request.waypoints:
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _cancel_callback(self, _goal_handle):
        self._stop_motion("cancelled")
        return CancelResponse.ACCEPT

    def _execute_follow_path(self, goal_handle):
        with self._path_lock:
            if self.mode == self.MODE_ESTOP:
                goal_handle.abort()
                result = FollowPath.Result()
                result.success = False
                result.completion_reason = "estopped"
                return result

            self._goal_handle = goal_handle
            self._goal_done.clear()
            self._completion_reason = ""
            params = self._controller_params()
            params["lateral_offset"] = float(goal_handle.request.lateral_offset)
            params["speed_multiplier"] = float(goal_handle.request.speed_multiplier or 1.0)
            self.racing_config.set_offset(params["lateral_offset"])
            self.racing_config.set_speed_multiplier(params["speed_multiplier"])
            self.racing_config.set_loop(bool(goal_handle.request.loop))
            self.follower = PathFollower(
                waypoints=[(wp.x, wp.y) for wp in goal_handle.request.waypoints],
                **params,
            )
            self.follower.loop_enabled = bool(goal_handle.request.loop)
            self.mode = self.MODE_FOLLOW_PATH
            self.active_control_source = "autonomy"

        feedback = FollowPath.Feedback()
        while rclpy.ok() and not self._goal_done.wait(0.1):
            if goal_handle.is_cancel_requested:
                with self._path_lock:
                    self._stop_motion("cancelled")
                goal_handle.canceled()
                result = FollowPath.Result()
                result.success = False
                result.completion_reason = "cancelled"
                return result
            feedback.waypoint_index = int(self._path_progress.waypoint_index)
            feedback.total_waypoints = int(self._path_progress.total_waypoints)
            feedback.distance_to_target = float(self._path_progress.distance_to_target)
            feedback.throttle = float(self._path_progress.throttle)
            feedback.mode = self.mode
            goal_handle.publish_feedback(feedback)

        result = FollowPath.Result()
        success = self._completion_reason in {"completed", "finished"}
        result.success = success
        result.completion_reason = self._completion_reason or "stopped"
        if success:
            goal_handle.succeed()
        else:
            goal_handle.abort()
        return result

    def _controller_params(self) -> dict:
        return {
            "waypoint_tolerance": 0.20,
            "turn_in_place_threshold": 65.0,
            "proportional_gain": 2.8,
            "max_turn_rate": 85.0,
            "use_prediction": True,
            "estimated_delay_ms": 100,
            "curvature_speed_gain": 0.65,
            "min_speed_ratio": 0.20,
            "slow_down_distance": 0.5,
            "path_simplification_tolerance": 0.06,
            "min_waypoint_separation": 0.15,
            "segment_pass_distance": 0.09,
            "segment_pass_lateral_factor": 1.7,
            "waypoint_approach_slowdown": 0.30,
            "corner_keep_angle_deg": 22.0,
            "intermediate_corner_slowdown_deg": 90.0,
            "look_ahead_distance": 0.4,
            "throttle_ramp_rate": 0.9,
            "control_loop_hz": self.control_hz,
        }

    def _on_heartbeat(self, _msg: Header) -> None:
        self.telemetry.last_heartbeat_monotonic = time.monotonic()

    def _on_pose(self, msg: PoseStamped) -> None:
        pos = msg.pose.position
        ori = msg.pose.orientation
        self.telemetry.x = -float(pos.x) if self.pose_flip_x else float(pos.x)
        self.telemetry.y = float(pos.y)
        self.telemetry.yaw = _quat_to_yaw(ori.x, ori.y, ori.z, ori.w)
        self.telemetry.last_pose_monotonic = time.monotonic()
        pose_msg = PoseStamped()
        pose_msg.header = msg.header
        pose_msg.pose = msg.pose
        pose_msg.pose.position.x = self.telemetry.x
        pose_msg.pose.position.y = self.telemetry.y
        self.pose_pub.publish(pose_msg)

    def _on_battery(self, msg: BatteryState) -> None:
        self.telemetry.battery_voltage = float(msg.voltage)
        self.telemetry.battery_percentage = float(msg.percentage * 100.0) if msg.percentage >= 0 else float("nan")

    def _on_imu(self, msg: Imu) -> None:
        self.telemetry.imu_yaw = _quat_to_yaw(
            msg.orientation.x,
            msg.orientation.y,
            msg.orientation.z,
            msg.orientation.w,
        )

    def _on_range(self, sensor_name: str, msg: Range) -> None:
        setattr(self.telemetry, f"range_{sensor_name}", float(msg.range))

    def _handle_set_mode(self, request: SetMode.Request, response: SetMode.Response):
        new_mode = request.mode.strip().upper()
        valid = {self.MODE_IDLE, self.MODE_MANUAL, self.MODE_ESTOP, self.MODE_FAULT}
        if new_mode not in valid:
            response.success = False
            response.message = f"Unsupported mode: {request.mode}"
            return response

        if new_mode == self.MODE_ESTOP:
            self.estopped = True
            self.mode = self.MODE_ESTOP
            self._stop_motion("estopped")
        elif new_mode == self.MODE_IDLE:
            self.estopped = False
            self.mode = self.MODE_IDLE
            self._stop_motion("idle")
        elif new_mode == self.MODE_MANUAL:
            if self.estopped:
                response.success = False
                response.message = "Cannot enter MANUAL while estopped; set IDLE first"
                return response
            self.mode = self.MODE_MANUAL
            self.active_control_source = "supervisor"
        else:  # self.MODE_FAULT
            self.mode = self.MODE_FAULT
            self._stop_motion("fault")
        response.success = True
        response.message = f"Mode set to {self.mode}"
        return response

    def _handle_set_racing(self, request: SetRacingConfig.Request, response: SetRacingConfig.Response):
        self.racing_config.set_offset(float(request.lateral_offset))
        self.racing_config.set_speed_multiplier(float(request.speed_multiplier))
        self.racing_config.set_loop(bool(request.loop_path))
        if self.follower is not None:
            self.follower.set_lateral_offset(self.racing_config.lateral_offset)
            self.follower.speed_multiplier = self.racing_config.speed_multiplier
            self.follower.loop_enabled = self.racing_config.loop_path
        response.success = True
        response.message = "Racing config updated"
        return response

    def _handle_estop(self, _request: Trigger.Request, response: Trigger.Response):
        self.estopped = True
        self._stop_motion("estopped")
        self.mode = self.MODE_ESTOP
        response.success = True
        response.message = "Emergency stop activated"
        return response

    def _handle_cancel(self, _request: Trigger.Request, response: Trigger.Response):
        self._stop_motion("cancelled")
        self.mode = self.MODE_ESTOP if self.estopped else self.MODE_IDLE
        response.success = True
        response.message = "Motion cancelled"
        return response

    def _handle_clear(self, _request: Trigger.Request, response: Trigger.Response):
        self._stop_motion("cleared")
        self.mode = self.MODE_ESTOP if self.estopped else self.MODE_IDLE
        response.success = True
        response.message = "Path cleared"
        return response

    def _status_tick(self) -> None:
        now = time.monotonic()
        pose_age = now - self.telemetry.last_pose_monotonic if self.telemetry.last_pose_monotonic else float("inf")
        heartbeat_age = now - self.telemetry.last_heartbeat_monotonic if self.telemetry.last_heartbeat_monotonic else float("inf")
        status = RobotStatus()
        status.robot_name = self.robot.name
        status.robot_type = self.robot.robot_type
        status.mode = self.mode
        status.online = True
        status.healthy = self.mode != self.MODE_FAULT
        status.estopped = self.estopped
        status.path_active = self.mode == self.MODE_FOLLOW_PATH
        status.pose_fresh = pose_age <= self.pose_timeout
        status.active_control_source = self.active_control_source
        status.fault_reason = self.telemetry.fault_reason
        status.x = float(self.telemetry.x)
        status.y = float(self.telemetry.y)
        status.yaw = float(self.telemetry.yaw)
        status.battery_percentage = float(self.telemetry.battery_percentage)
        status.battery_voltage = float(self.telemetry.battery_voltage)
        status.imu_yaw = float(self.telemetry.imu_yaw)
        status.range_fl = float(self.telemetry.range_fl)
        status.range_fr = float(self.telemetry.range_fr)
        status.range_rl = float(self.telemetry.range_rl)
        status.range_rr = float(self.telemetry.range_rr)
        status.stamp = _stamp_now(self)
        self.status_pub.publish(status)

        diag = RobotDiagnostics()
        diag.robot_name = self.robot.name
        diag.pose_topic = self.robot.resolved_pose_topic() or ""
        diag.battery_topic = self.robot.battery_topic or ""
        diag.imu_topic = self.robot.imu_topic or ""
        diag.odometry_topic = self.robot.odometry_topic or ""
        diag.ranges_topic_prefix = f"{self.robot.namespace}/range"
        diag.last_pose_age_sec = float(pose_age if math.isfinite(pose_age) else -1.0)
        diag.last_heartbeat_age_sec = float(heartbeat_age if math.isfinite(heartbeat_age) else -1.0)
        diag.has_battery = math.isfinite(self.telemetry.battery_voltage)
        diag.has_imu = math.isfinite(self.telemetry.imu_yaw)
        diag.has_ranges = any(math.isfinite(v) for v in [self.telemetry.range_fl, self.telemetry.range_fr, self.telemetry.range_rl, self.telemetry.range_rr])
        diag.has_path = self.follower is not None
        diag.mode = self.mode
        diag.fault_reason = self.telemetry.fault_reason
        diag.stamp = _stamp_now(self)
        self.diag_pub.publish(diag)

        self._path_progress.robot_name = self.robot.name
        self._path_progress.stamp = _stamp_now(self)
        self.progress_pub.publish(self._path_progress)

    def _control_tick(self) -> None:
        now = time.monotonic()
        pose_age = now - self.telemetry.last_pose_monotonic if self.telemetry.last_pose_monotonic else float("inf")
        heartbeat_age = now - self.telemetry.last_heartbeat_monotonic if self.telemetry.last_heartbeat_monotonic else float("inf")

        if self.mode in {self.MODE_MANUAL, self.MODE_FOLLOW_PATH} and heartbeat_age > self.heartbeat_timeout:
            self.telemetry.fault_reason = "supervisor heartbeat timeout"
            self._stop_motion("heartbeat_timeout")
            self.mode = self.MODE_FAULT if self.mode == self.MODE_FOLLOW_PATH else self.MODE_IDLE
            return

        if self.mode == self.MODE_FOLLOW_PATH:
            if pose_age > self.pose_timeout:
                self.telemetry.fault_reason = "pose timeout"
                self._stop_motion("pose_timeout")
                self.mode = self.MODE_FAULT
                return
            if self.follower is None or self.estopped:
                self._stop_motion("stopped")
                return

            self.follower.update_state(self.telemetry.x, self.telemetry.y, self.telemetry.yaw, time.time())
            command = self.follower.compute_command()
            state = self.follower.get_state()
            self._path_progress.active = True
            self._path_progress.waypoint_index = int(state.get("waypoint_index", 0) or 0)
            self._path_progress.total_waypoints = int(state.get("total_waypoints", 0) or 0)
            self._path_progress.distance_to_target = float(state.get("distance_to_target", 0.0) or 0.0)

            if self.follower.is_complete() or command is None:
                self._stop_motion("completed")
                self.mode = self.MODE_IDLE
                return

            throttle, turn_rate_deg = command
            self._path_progress.throttle = float(throttle)
            self._publish_cmd_vel(throttle, turn_rate_deg)

    def _publish_cmd_vel(self, throttle: float, turn_rate_deg: float) -> None:
        twist = Twist()
        twist.linear.x = max(-self.robot.max_linear, min(self.robot.max_linear, float(throttle) * self.robot.max_linear))
        angular = math.radians(float(turn_rate_deg))
        twist.angular.z = max(-self.robot.max_angular, min(self.robot.max_angular, angular))
        self._publish_twist(twist)

    def _stop_motion(self, reason: str) -> None:
        self._publish_twist(Twist())
        self._path_progress.active = False
        self._path_progress.throttle = 0.0
        self._path_progress.completion_reason = reason
        self._completion_reason = reason
        if self.follower is not None:
            self.follower.reset()
            self.follower = None
        self.active_control_source = "none" if self.mode != self.MODE_MANUAL else "supervisor"
        self._goal_done.set()

    def _publish_twist(self, twist: Twist) -> None:
        if self.robot.uses_stamped_cmd_vel():
            stamped = TwistStamped()
            stamped.header.stamp = _stamp_now(self)
            stamped.twist = twist
            self.cmd_pub.publish(stamped)
            return
        self.cmd_pub.publish(twist)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = HydraRobotAgent()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
