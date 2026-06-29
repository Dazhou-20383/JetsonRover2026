import base64
import json
import os
import socket
import signal

import cv2
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import Pose2D, Twist
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Float32MultiArray, String


class Dashboard(Node):
    def __init__(self):
        super().__init__('dashboard_node')

        self.declare_parameter('socket_host', os.environ.get('DASHBOARD_SOCKET_HOST', '10.42.0.221'))
        self.declare_parameter('socket_port', int(os.environ.get('DASHBOARD_SOCKET_PORT', '9000')))
        self.declare_parameter('send_frequency_hz', 10.0)

        self.socket_host = self.get_parameter('socket_host').value
        self.socket_port = int(self.get_parameter('socket_port').value)
        self.send_frequency_hz = float(self.get_parameter('send_frequency_hz').value)

        self.latest_velocity = {
            'linear': 0.0,
            'angular': 0.0,
        }
        self.latest_motor_commands = []
        self.latest_pose = {
            'x': 0.0,
            'y': 0.0,
            'theta': 0.0,
        }
        self.latest_image = None

        self.agent_state = {}

        self.agent_sub = self.create_subscription(
            String,
            '/agent/state',
            self.agent_callback,
            10,
        )

        self.vel_sub = self.create_subscription(
            Twist,
            '/motion/cmd_vel',
            self.vel_callback,
            10,
        )
        self.motor_sub = self.create_subscription(
            Float32MultiArray,
            '/motion/motor_commands',
            self.motor_callback,
            10,
        )
        self.pose_sub = self.create_subscription(
            Pose2D,
            '/robot/pose',
            self.pose_callback,
            10,
        )

        self.cv_bridge = CvBridge()
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10,
        )

        self.socket_client = None
        self._connect_socket()

        timer_period = 1.0 / self.send_frequency_hz if self.send_frequency_hz > 0.0 else 0.1
        self.send_timer = self.create_timer(timer_period, self.send_current_data)

        self.get_logger().info('Dashboard Node has been started.')

    def _connect_socket(self):
        self._close_socket()

        try:
            self.socket_client = socket.create_connection(
                (self.socket_host, self.socket_port),
                timeout=5.0,
            )
            self.socket_client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.get_logger().info(
                f'Connected to dashboard socket at {self.socket_host}:{self.socket_port}'
            )
        except OSError as exc:
            self.socket_client = None
            self.get_logger().warning(
                f'Unable to connect to {self.socket_host}:{self.socket_port}: {exc}'
            )

    def _close_socket(self):
        if self.socket_client is not None:
            try:
                self.socket_client.close()
            except OSError:
                pass
            finally:
                self.socket_client = None

    def _build_payload(self):
        payload = {
            'agent_state': self.agent_state,
            'velocity': self.latest_velocity,
            'motor_commands': self.latest_motor_commands,
            'pose': self.latest_pose,
            'image': self.latest_image,
            'stamp_ns': self.get_clock().now().nanoseconds,
        }
        return json.dumps(payload, separators=(',', ':')) + '\n'

    def send_current_data(self):
        if self.socket_client is None:
            self._connect_socket()
            if self.socket_client is None:
                return

        try:
            self.socket_client.sendall(self._build_payload().encode('utf-8'))
        except OSError as exc:
            self.get_logger().warning(f'Socket send failed: {exc}')
            self._connect_socket()

    def agent_callback(self, msg):
        try:
            self.agent_state = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().error(f'Failed to decode agent state JSON: {exc}')

    def vel_callback(self, msg):
        self.latest_velocity = {
            'linear': msg.linear.x,
            'angular': msg.angular.z,
        }

    def motor_callback(self, msg):
        self.latest_motor_commands = list(msg.data)

    def pose_callback(self, msg):
        self.latest_pose = {
            'x': msg.x,
            'y': msg.y,
            'theta': msg.theta,
        }

    def image_callback(self, msg):
        try:
            cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            success, encoded_image = cv2.imencode(
                '.jpg',
                cv_image,
                [int(cv2.IMWRITE_JPEG_QUALITY), 70],
            )

            if success:
                self.latest_image = {
                    'encoding': 'jpg',
                    'width': int(cv_image.shape[1]),
                    'height': int(cv_image.shape[0]),
                    'data': base64.b64encode(encoded_image.tobytes()).decode('ascii'),
                }
            else:
                self.get_logger().warning('Failed to encode image for socket transport.')
        except Exception as exc:
            self.get_logger().error(f'Image conversion failed: {exc}')

    def destroy_node(self):
        self._close_socket()
        return super().destroy_node()


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
    node = Dashboard()
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
