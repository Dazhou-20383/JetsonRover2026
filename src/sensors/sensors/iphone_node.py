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

    def poll_socket(self):
        try:
            data, _ = self.sock.recvfrom(4096)
        except BlockingIOError:
            return

        payload = json.loads(data.decode('utf-8'))
        payload_type = payload.get('type')

        if payload_type == 'route_guide':
            self.publish_route_direction(payload)
            return

        if {'x', 'y', 'yaw'}.issubset(payload):
            self.publish_pose(payload)
            return

        self.get_logger().debug(f'Ignoring unsupported payload: {payload}')

    def publish_pose(self, payload):
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

    def publish_route_direction(self, payload):
        steps = payload.get('steps', [])
        if not steps:
            self.get_logger().debug('Received route_guide payload without actionable steps')
            return

        next_step = steps[0]
        instruction = str(next_step.get('instruction', '')).strip()
        if not instruction:
            cardinal = str(next_step.get('cardinal', '')).strip()
            distance_m = next_step.get('distance_m')
            if cardinal and distance_m is not None:
                instruction = f'{cardinal} for {distance_m} m'
            elif cardinal:
                instruction = cardinal
            else:
                self.get_logger().debug('Received route_guide step without direction text')
                return

        direction_msg = String()
        direction_msg.data = instruction
        self.publisher_directions.publish(direction_msg)


def main(args=None):
    rclpy.init(args=args)
    node = IPhonePoseNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
