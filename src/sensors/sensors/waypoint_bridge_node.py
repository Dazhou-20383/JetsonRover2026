import json
import signal
import socket
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class WaypointBridgeNode(Node):
    """Receives MapKit-derived waypoint/route messages from the iOS
    LocalizationBridge app over TCP and republishes them as tagged JSON
    for downstream ROS2/VLM consumers.

    This is the TCP counterpart to iphone_pose_node.py's UDP pose stream:
    the AR pose is latency-sensitive and loss-tolerant (a dropped sample
    is immediately superseded by the next one at 5 Hz), while a manual
    goal or route guide is a rare, one-shot, loss-sensitive message, so
    it travels over TCP instead, where the OS guarantees delivery and
    ordering.
    """

    HOST = '0.0.0.0'
    PORT = 5006

    def __init__(self):
        super().__init__('waypoint_bridge_node')

        self.manual_goal_pub = self.create_publisher(String, '/bridge/manual_goal_json', 10)
        self.route_guide_pub = self.create_publisher(String, '/bridge/route_guide_json', 10)

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.HOST, self.PORT))
        self._server_socket.listen(1)

        self._stop_event = threading.Event()
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

        self.get_logger().info(f'Listening for iPhone waypoint/route messages on TCP port {self.PORT}')

    def _accept_loop(self):
        while not self._stop_event.is_set():
            try:
                self._server_socket.settimeout(1.0)
                conn, addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            self.get_logger().info(f'Waypoint bridge: connection from {addr}')
            threading.Thread(target=self._handle_connection, args=(conn,), daemon=True).start()

    def _handle_connection(self, conn: socket.socket):
        # Messages are newline-delimited JSON, since TCP is a byte stream
        # with no built-in message boundaries (unlike the UDP pose path,
        # where each datagram is already exactly one message).
        buffer = b''
        with conn:
            conn.settimeout(5.0)
            while not self._stop_event.is_set():
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break

                if not chunk:
                    break

                buffer += chunk
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if line.strip():
                        self._dispatch(line)

    def _dispatch(self, line: bytes):
        try:
            raw_json = line.decode('utf-8')
            payload = json.loads(raw_json)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            self.get_logger().warning(f'Waypoint bridge: dropping malformed message ({error})')
            return

        message_type = payload.get('type')

        if message_type == 'manual_goal':
            self.manual_goal_pub.publish(String(data=raw_json))
            self.get_logger().info(
                f"Waypoint bridge: manual_goal lat={payload.get('latitude')} lon={payload.get('longitude')}"
            )
        elif message_type == 'route_guide':
            self.route_guide_pub.publish(String(data=raw_json))
            self.get_logger().info('Waypoint bridge: route_guide received')
        else:
            self.get_logger().warning(f'Waypoint bridge: unknown message type {message_type!r}')

    def destroy_node(self):
        self._stop_event.set()
        try:
            self._server_socket.close()
        except OSError:
            pass
        super().destroy_node()


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
    node = WaypointBridgeNode()
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
