import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class VideoLogger(Node):
    def __init__(self):
        super().__init__('video_logger')
        self.cv_bridge = CvBridge()
        self.get_logger().info('Video Logger Node has been started.')

        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_compressed',
            self.image_callback,
            10
        )

    def image_callback(self, msg):
        # Process the received image message
        img = msg.data

        try:
            # Convert ROS Image to OpenCV image
            cv_image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            # Display image
            cv2.imshow("ROS2 Image", cv_image)
            cv2.waitKey(1)

        except Exception as e:
            self.get_logger().error(f"Conversion failed: {e}")
    
def main(args=None):
    rclpy.init(args=args)
    video_logger = VideoLogger()
    rclpy.spin(video_logger)
    video_logger.destroy_node()
    rclpy.shutdown()