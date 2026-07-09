import json
import math
import socket
import signal

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class ManuelController(Node):
    def __init__(self):
        super().__init__('manuel_controller_node')

        self.publisher = self.create_publisher(Twist, '/motion/cmd_vel', 10)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', 8080))  # same port as Swift app
        self.sock.setblocking(False)

        self.timer = self.create_timer(0.02, self.poll_socket)

        self.get_logger().info('Listening for joystick input on UDP port 8080')

    def poll_socket(self):
        try:
            data, _ = self.sock.recvfrom(4096)
        except BlockingIOError:
            return

        payload = json.loads(data.decode('utf-8'))
        linear = float(payload['velocity'])
        angular = float(payload['angularVelocity'])

        msg = Twist()

        msg.linear.x = linear
        msg.linear.y = 0
        msg.angular.z = angular

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
    node = ManuelController()
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