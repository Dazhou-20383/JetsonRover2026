import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.publisher_ = self.create_publisher(Image, 'camera/image_compressed', 10)
        self.bridge = CvBridge()

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

        self.timer = self.create_timer(0.03, self.publish_frame)  # ~30 FPS

    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return
        #frame = cv2.resize(frame, (640, 360)) #<-- Resize here
        # Convert to ROS Image
        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        self.publisher_.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()