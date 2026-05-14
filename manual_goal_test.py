import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped


class ManualGoalPublisher(Node):
    def __init__(self):
        super().__init__('manual_goal_publisher')

        self.publisher = self.create_publisher(PoseStamped, '/global_goal', 10)
        self.timer = self.create_timer(1.0, self.publish_goal)

        self.goal_x = 8.0
        self.goal_y = -10.0
        self.goal_yaw = -math.pi / 2

    def publish_goal(self):
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'

        msg.pose.position.x = self.goal_x
        msg.pose.position.y = self.goal_y

        msg.pose.orientation.z = math.sin(self.goal_yaw / 2)
        msg.pose.orientation.w = math.cos(self.goal_yaw / 2)

        self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ManualGoalPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()