import rclpy
from rclpy.node import Node
import cv2
import socket
import struct
import pickle

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        
        # Configuration
        self.jetson_ip = '0.0.0.0' # Listen on all interfaces
        self.port = 9999

        # Initialize Socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.jetson_ip, self.port))
        self.server_socket.listen(5)
        self.get_logger().info(f"[*] Jetson Sender started. Listening on port {self.port}...")

        # Block until connection is accepted
        self.client_socket, self.addr = self.server_socket.accept()
        self.get_logger().info(f"[*] Connection from {self.addr} accepted.")

        pipeline = (
            "v4l2src device=/dev/video0 ! "
            "image/jpeg, width=1280, height=720, framerate=30/1 ! "
            "jpegdec ! "
            "nvvidconv ! "
            "video/x-raw, width=640, height=360, format=BGRx ! "  # <-- resize here
            "videoconvert ! "
            "video/x-raw, format=BGR ! "
            "appsink drop=1 sync=0"
        )

        self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

        self.timer = self.create_timer(0.03, self.send_frame)  # ~30 FPS

    def send_frame(self):
        ret, frame = self.cap.read()
        if not ret:
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
            self.get_logger().error(f"Error: {e}")

    def destroy_node(self):
        self.cap.release()
        try:
            self.client_socket.close()
            self.server_socket.close()
        except Exception:
            pass
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()