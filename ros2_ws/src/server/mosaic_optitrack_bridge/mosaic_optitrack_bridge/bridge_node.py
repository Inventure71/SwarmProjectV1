from __future__ import annotations

import rclpy
from geometry_msgs.msg import PoseStamped
from mosaic_common import load_fleet_config
from rclpy.node import Node


class MosaicOptitrackBridge(Node):
    def __init__(self) -> None:
        super().__init__("mosaic_optitrack_bridge")
        self.declare_parameter("config_path", "")
        cfg_path = self.get_parameter("config_path").get_parameter_value().string_value or None
        self.fleet = load_fleet_config(cfg_path)
        self.publishers = {}
        self.subscriptions = []
        configured = 0

        for robot in self.fleet.robots.values():
            source_topic = robot.pose_topic
            target_topic = robot.resolved_pose_topic()
            if not source_topic or not target_topic or source_topic == target_topic:
                continue
            publisher = self.create_publisher(PoseStamped, target_topic, 10)
            self.publishers[target_topic] = publisher
            sub = self.create_subscription(
                PoseStamped,
                source_topic,
                lambda msg, topic=target_topic: self.publishers[topic].publish(msg),
                10,
            )
            self.subscriptions.append(sub)
            configured += 1

        self.get_logger().info(f"OptiTrack relay ready with {configured} configured mappings")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MosaicOptitrackBridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
