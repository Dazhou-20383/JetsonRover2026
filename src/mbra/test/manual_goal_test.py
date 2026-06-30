import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point


class ManualGoalPublisher(Node):
    def __init__(self):
        super().__init__('manual_goal_publisher')

        self.publisher = self.create_publisher(Point, '/mbra/waypoints', 10)
        self.timer = self.create_timer(1.0, self.publish_goal)

        self.goal_x = 80.0
        self.goal_y = -10.0
        self.goal_yaw = 0

    def publish_goal(self):
        msg = Point()

        msg.x = self.goal_x
        msg.y = self.goal_y
        msg.z = self.goal_yaw
        self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ManualGoalPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()