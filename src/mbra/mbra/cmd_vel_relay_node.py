#!/usr/bin/env python3

import rclpy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from rclpy.node import Node


class CmdVelRelayNode(Node):
    def __init__(self) -> None:
        super().__init__('cmd_vel_relay_node')

        self._publisher = self.create_publisher(Bool, '/motion/cmd_vel', 10)
        self._enable_mbra_pub = self.create_publisher(Twist, '/mbra/enable', 10)
        self._subscription = self.create_subscription(
            Twist,
            '/mbra/cmd_vel',
            self._cmd_vel_callback,
            10,
        )

        self.get_logger().info('Relaying /mbra/cmd_vel -> /motion/cmd_vel')

    def _cmd_vel_callback(self, msg: Twist) -> None:
        self._publisher.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CmdVelRelayNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()