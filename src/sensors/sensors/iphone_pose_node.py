import json
import math
import socket
import signal

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose2D


class IPhonePoseNode(Node):
    def __init__(self):
        super().__init__('iphone_pose_node')

        self.publisher = self.create_publisher(Pose2D, '/robot_pose', 10)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', 5005))  # same port as Swift app
        self.sock.setblocking(False)

        self.timer = self.create_timer(0.02, self.poll_socket)

        self.get_logger().info('Listening for iPhone pose on UDP port 5005')

    def poll_socket(self):
        try:
            data, _ = self.sock.recvfrom(4096)
        except BlockingIOError:
            return

        payload = json.loads(data.decode('utf-8'))
        x = float(payload['x'])
        y = float(payload['y'])
        yaw = float(payload['yaw'])

        msg = Pose2D()

        msg.x = x
        msg.y = y
        msg.theta = yaw

        self.publisher.publish(msg)


def _install_shutdown_handlers(node):
    def _handle_shutdown(signum, frame):
        if rclpy.ok():
            node.get_logger().info(f'Received signal {signum}, shutting down.')
            rclpy.try_shutdown()

    signal.signal(signal.SIGINT, _handle_shutdown)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _handle_shutdown)


def main(args=None):
    rclpy.init(args=args)
    node = IPhonePoseNode()
    _install_shutdown_handlers(node)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()