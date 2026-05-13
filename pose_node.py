import rclpy
from rclpy.node import Node

from geometry_msgs.msg import PoseStamped
from tf_transformations import quaternion_from_euler

class PoseNode(Node):

    def __init__(self):
        super().__init__('pose_node')

        self.publisher_ = self.create_publisher(
            PoseStamped,
            '/robot_pose',
            10
        )

        self.timer = self.create_timer(0.1, self.publish_pose)

        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0

    def publish_pose(self):

        msg = PoseStamped()

        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"

        # fake motion
        self.x += 0.02

        msg.pose.position.x = self.x
        msg.pose.position.y = self.y
        msg.pose.position.z = 0.0

        q = quaternion_from_euler(0, 0, self.yaw)

        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]

        self.publisher_.publish(msg)

def main(args=None):

    rclpy.init(args=args)

    node = PoseNode()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()