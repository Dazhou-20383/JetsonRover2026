import rclpy
from rclpy.node import Node

from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import Vector3

from tf_transformations import euler_from_quaternion

import numpy as np

class RelativeGoalNode(Node):

    def __init__(self):

        super().__init__('relative_goal_node')

        self.pose_msg = None
        self.goal_msg = None

        self.subscription_pose = self.create_subscription(
            PoseStamped,
            '/robot_pose',
            self.pose_callback,
            10
        )

        self.subscription_goal = self.create_subscription(
            PoseStamped,
            '/global_goal',
            self.goal_callback,
            10
        )

        self.publisher_ = self.create_publisher(
            Vector3,
            '/relative_goal',
            10
        )

        self.timer = self.create_timer(0.1, self.compute_relative_goal)

    def pose_callback(self, msg):
        self.pose_msg = msg

    def goal_callback(self, msg):
        self.goal_msg = msg

    def compute_relative_goal(self):

        if self.pose_msg is None or self.goal_msg is None:
            return

        robot_x = self.pose_msg.pose.position.x
        robot_y = self.pose_msg.pose.position.y

        q = self.pose_msg.pose.orientation

        quat = [q.x, q.y, q.z, q.w]

        _, _, robot_yaw = euler_from_quaternion(quat)

        goal_x = self.goal_msg.pose.position.x
        goal_y = self.goal_msg.pose.position.y

        dx = goal_x - robot_x
        dy = goal_y - robot_y

        # rotate into robot frame
        dx_rel = np.cos(-robot_yaw) * dx - np.sin(-robot_yaw) * dy
        dy_rel = np.sin(-robot_yaw) * dx + np.cos(-robot_yaw) * dy

        msg = Vector3()

        msg.x = float(dx_rel)
        msg.y = float(dy_rel)
        msg.z = 0.0

        self.publisher_.publish(msg)

def main(args=None):

    rclpy.init(args=args)

    node = RelativeGoalNode()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()