import os
import pickle
import signal
import socket
import struct
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from custom_msgs.srv import ImageSrv
from cv_bridge import CvBridge

DEVICE_PATH = '/dev/video0'
CAMERA_WARMUP_TIMEOUT_SEC = 2.0
IPHONE_CAMERA_PORT = 5007


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')

        self.bridge = CvBridge()
        self.image_publisher = self.create_publisher(Image, '/camera/image_raw', 10)
        self.action_srv = self.create_service(ImageSrv, '/sensor/image', self.image_service_handler)
        self.current_frame = None

        # Only one of these two pipelines is ever started per run, depending on
        # whether the onboard camera is actually present and producing frames.
        self.cap = None
        self.server_socket = None
        self.client_socket = None
        self.iphone_socket = None

        self.cap = self._open_local_camera()
        if self.cap is not None:
            self.get_logger().info('Local camera device detected; using onboard camera.')
            self._start_local_camera_pipeline()
        else:
            self.get_logger().warn('No local camera device detected; falling back to iPhone camera stream.')
            self._start_iphone_camera_fallback()

    def _open_local_camera(self):
        if not os.path.exists(DEVICE_PATH):
            return None

        pipeline = (
            f"v4l2src device={DEVICE_PATH} ! "
            "image/jpeg, width=1280, height=720, framerate=30/1 ! "
            "jpegdec ! "
            "nvvidconv ! "
            "video/x-raw, width=640, height=360, format=BGRx ! "  # <-- resize here
            "videoconvert ! "
            "video/x-raw, format=BGR ! "
            "appsink drop=1 sync=0"
        )

        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            cap.release()
            return None

        # isOpened() can report True even when a GStreamer pipeline never
        # actually produces frames (e.g. the device file exists but the
        # sensor isn't responding), so confirm at least one frame arrives
        # before trusting this source.
        deadline = time.monotonic() + CAMERA_WARMUP_TIMEOUT_SEC
        while time.monotonic() < deadline:
            ret, _ = cap.read()
            if ret:
                return cap
            time.sleep(0.1)

        cap.release()
        return None

    def _start_local_camera_pipeline(self):
        # Configuration
        self.jetson_ip = '0.0.0.0'  # Listen on all interfaces
        self.port = 9999

        # Initialize Socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.jetson_ip, self.port))
        self.server_socket.listen(5)
        self.server_socket.settimeout(0.0)
        self.get_logger().info(f"[*] Jetson Sender started. Listening on port {self.port}...")

        self.timer = self.create_timer(0.03, self.send_frame)  # ~30 FPS
        self.publish_timer = self.create_timer(1.0, self.publish_frame)

    def _start_iphone_camera_fallback(self):
        # Mirrors iphone_pose_node.py's non-blocking-socket + timer-poll
        # pattern: a UDP datagram is already exactly one message (one JPEG
        # frame here), so no accept loop or framing is needed.
        self.iphone_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.iphone_socket.bind(('0.0.0.0', IPHONE_CAMERA_PORT))
        self.iphone_socket.setblocking(False)
        self.iphone_poll_timer = self.create_timer(0.02, self._poll_iphone_camera_socket)
        self.get_logger().info(f'Listening for iPhone camera frames on UDP port {IPHONE_CAMERA_PORT}')

    def _poll_iphone_camera_socket(self):
        try:
            data, _ = self.iphone_socket.recvfrom(65536)
        except BlockingIOError:
            return

        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            self.get_logger().warning('Dropping malformed iPhone camera frame.')
            return

        self.current_frame = frame
        # The phone only sends at ~5 Hz, so publishing on receipt (rather
        # than on a separate timer) already matches the target publish rate.
        self.publish_frame()

    def send_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return
            
        self.current_frame = frame
        
        if self.client_socket is None:
            try:
                self.client_socket, self.addr = self.server_socket.accept()
                self.client_socket.settimeout(0.0)
                self.get_logger().info(f"[*] Connection from {self.addr} accepted.")
            except (BlockingIOError, socket.timeout):
                return
            except Exception as e:
                self.get_logger().error(f"Error accepting connection: {e}")
                return
            
        try:
            # 1. Compress frame to JPEG (Quality 0-100, lower is faster)
            result, frame_encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            data = pickle.dumps(frame_encoded)

            # 2. Pack the size of the message first (L = unsigned long)
            message_size = struct.pack("Q", len(data))

            # 3. Send size then data
            self.client_socket.sendall(message_size + data)
        except Exception as e:
            self.get_logger().error(f"Socket send error: {e}")
            self.client_socket.close()
            self.client_socket = None

    def publish_frame(self):
        if self.current_frame is not None:
            try:
                msg = self.bridge.cv2_to_imgmsg(self.current_frame, encoding="bgr8")
                self.image_publisher.publish(msg)
            except Exception as e:
                self.get_logger().error(f"Error publishing frame: {e}")

    def image_service_handler(self, request, response):
        if self.current_frame is not None:
            try:
                response.image = self.bridge.cv2_to_imgmsg(self.current_frame, encoding="bgr8")
                response.success = True
            except Exception as e:
                response.error = f"Error converting frame to Image message: {e}"
                response.success = False
                self.get_logger().error(f"Error converting frame to Image message: {e}")
        else:
            response.error = "No frame available to serve."
            response.success = False
            self.get_logger().warn("No frame available to serve.")

        return response

    def destroy_node(self):
        if self.cap:
            self.cap.release()
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        if self.iphone_socket:
            try:
                self.iphone_socket.close()
            except Exception:
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
    node = CameraNode()
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