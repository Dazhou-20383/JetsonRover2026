import asyncio
import json
import signal
import threading
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

import websockets


class ManuelController(Node):
    def __init__(self):
        super().__init__('manuel_controller_node')

        self.publisher = self.create_publisher(
            Twist,
            '/motion/cmd_vel',
            10
        )

        self.client_connected = False
        self.last_command_time = time.time()

        self.loop = asyncio.new_event_loop()

        self.ws_thread = threading.Thread(
            target=self.run_websocket_server,
            daemon=True
        )
        self.ws_thread.start()

        # watchdog timer
        self.timer = self.create_timer(
            0.05,
            self.check_timeout
        )

        self.get_logger().info(
            "WebSocket joystick server started on port 8080"
        )

    def run_websocket_server(self):
        asyncio.set_event_loop(self.loop)

        server = self.loop.run_until_complete(
            websockets.serve(
                self.websocket_handler,
                "0.0.0.0",
                8080
            )
        )

        self.loop.run_until_complete(server.wait_closed())


    async def websocket_handler(self, websocket):
        self.client_connected = True

        peer = websocket.remote_address

        self.get_logger().info(
            f"Joystick connected: {peer}"
        )

        try:
            async for message in websocket:

                try:
                    payload = json.loads(message)

                    linear = float(payload["velocity"])
                    angular = float(payload["angularVelocity"])

                    self.last_command_time = time.time()

                    cmd = Twist()
                    cmd.linear.x = linear
                    cmd.angular.z = angular

                    self.publisher.publish(cmd)

                except Exception as e:
                    self.get_logger().warn(
                        f"Invalid joystick packet: {e}"
                    )

        except websockets.ConnectionClosed:
            pass

        finally:
            self.client_connected = False

            self.get_logger().warn(
                "Joystick disconnected"
            )

            # immediately stop robot
            self.publisher.publish(Twist())


    def check_timeout(self):
        """
        Safety watchdog:
        Stop robot if no command received recently.
        """

        timeout = 0.5  # seconds

        if time.time() - self.last_command_time > timeout:

            if self.client_connected:
                self.get_logger().warn(
                    "Joystick timeout, stopping robot"
                )

            self.publisher.publish(Twist())

def install_shutdown_handlers(node):
    def shutdown(signum, frame):
        node.get_logger().info(
            "Shutting down"
        )
        rclpy.try_shutdown()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

def main(args=None):
    rclpy.init(args=args)

    node = ManuelController()

    install_shutdown_handlers(node)

    try:
        rclpy.spin(node)

    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()