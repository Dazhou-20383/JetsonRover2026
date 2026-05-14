import rclpy
from rclpy.node import Node

from geometry_msgs.msg import PoseStamped
from tf_transformations import quaternion_from_euler

class GoalNode(Node):

    def __init__(self):
        super().__init__('goal_node')

        self.publisher_ = self.create_publisher(
            PoseStamped,
            '/global_goal',
            10
        )

        self.timer = self.create_timer(0.5, self.publish_goal)

    def publish_goal(self):

        msg = PoseStamped()

        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"

        msg.pose.position.x = 8.0
        msg.pose.position.y = -10.0
        msg.pose.position.z = 0.0

        yaw = -1.57

        q = quaternion_from_euler(0, 0, yaw)

        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]

        self.publisher_.publish(msg)

def main(args=None):

    rclpy.init(args=args)

    node = GoalNode()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()