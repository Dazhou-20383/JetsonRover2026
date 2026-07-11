import asyncio
import json
import signal
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

import websockets


class EmergencyStop(Node):
    def __init__(self):
        super().__init__('stop_node')

        self.publisher = self.create_publisher(
            Bool,
            '/mbra/enable',
            10
        )

        self.client_connected = False
        self.last_command_time = time.time()

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

    def run_websocket_server(self):
        asyncio.run(self._serve_websocket())


    async def _serve_websocket(self):
        async with websockets.serve(
            self.websocket_handler,
            "0.0.0.0",
            8080
        ):
            self.get_logger().info(
                "WebSocket joystick server started on port 8080"
            )

            await asyncio.Future()


    async def websocket_handler(self, websocket):
        self.client_connected = True

        peer = websocket.remote_address

        self.get_logger().info(
            f"Emergency stop connected: {peer}"
        )

        try:
            async for message in websocket:

                try:
                    payload = json.loads(message)

                    enable = bool(payload["enable"])

                    self.last_command_time = time.time()

                    cmd = Bool()
                    cmd.data = enable

                    self.publisher.publish(cmd)

                except Exception as e:
                    self.get_logger().warn(
                        f"Invalid enable packet: {e}"
                    )

        except websockets.ConnectionClosed:
            pass

        finally:
            self.client_connected = False

            self.get_logger().warn(
                "Emergency stop disconnected"
            )

            # immediately stop robot
            self.publisher.publish(Bool(data=False))


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

            self.publisher.publish(Bool(data=False))

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

    node = EmergencyStop()

    install_shutdown_handlers(node)

    try:
        rclpy.spin(node)

    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()