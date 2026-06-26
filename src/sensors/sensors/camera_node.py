import rclpy
from rclpy.node import Node
import cv2
import socket
import struct
import pickle
from sensor_msgs.msg import Image
from action_msgs.srv import ImageSrv
from cv_bridge import CvBridge

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
        self.server_socket.settimeout(0.0)
        self.client_socket = None
        self.get_logger().info(f"[*] Jetson Sender started. Listening on port {self.port}...")

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
        
        self.bridge = CvBridge()
        self.image_publisher = self.create_publisher(Image, '/camera/image_raw', 10)
        self.action_srv = self.create_service(ImageSrv, '/sensor/image', self.image_service_handler)

        self.timer = self.create_timer(0.03, self.send_frame)  # ~30 FPS
        self.publish_timer = self.create_timer(1.0, self.publish_frame)
        self.current_frame = None

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
        self.cap.release()
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        try:
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