import json
import math
import socket

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String


class IPhonePoseNode(Node):
    def __init__(self):
        super().__init__('iphone_node')

        self.publisher_pose = self.create_publisher(PoseStamped, '/iphone/pose', 10)
        self.publisher_directions = self.create_publisher(String, '/iphone/directions', 10)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', 5005))  # same port as Swift app
        self.sock.setblocking(False)

        self.timer = self.create_timer(0.02, self.poll_socket)

        self.get_logger().info(
            'Listening for iPhone pose on UDP port 5005 and publishing to '
            '/iphone/pose and /iphone/directions'
        )

    @staticmethod
    def yaw_to_direction(yaw: float) -> str:
        directions = [
            'east',
            'north-east',
            'north',
            'north-west',
            'west',
            'south-west',
            'south',
            'south-east',
        ]
        normalized_yaw = yaw % (2.0 * math.pi)
        index = int(((normalized_yaw + (math.pi / 8.0)) % (2.0 * math.pi)) / (math.pi / 4.0))
        return directions[index]

    def poll_socket(self):
        try:
            data, _ = self.sock.recvfrom(4096)
        except BlockingIOError:
            return

        payload = json.loads(data.decode('utf-8'))
        x = float(payload['x'])
        y = float(payload['y'])
        yaw = float(payload['yaw'])

        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'

        msg.pose.position.x = x
        msg.pose.position.y = y
        msg.pose.position.z = 0.0

        msg.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.orientation.w = math.cos(yaw / 2.0)

        self.publisher_pose.publish(msg)

        direction_msg = String()
        direction_msg.data = self.yaw_to_direction(yaw)
        self.publisher_directions.publish(direction_msg)


def main(args=None):
    rclpy.init(args=args)
    node = IPhonePoseNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
