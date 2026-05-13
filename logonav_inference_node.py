import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Vector3, Twist
from sensor_msgs.msg import Image


class LogoNavInferenceNode(Node):
    def __init__(self):
        super().__init__('logonav_inference_node')

        self.latest_image = None
        self.latest_goal = None

        self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        self.create_subscription(Vector3, '/relative_goal', self.goal_callback, 10)

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # Run at 10 Hz
        self.timer = self.create_timer(0.1, self.run_inference)

        # TODO: insert researchers' model loading code here
        # self.model = load_model(...)

    def image_callback(self, msg):
        self.latest_image = msg

    def goal_callback(self, msg):
        self.latest_goal = msg

    def run_inference(self):
        if self.latest_image is None or self.latest_goal is None:
            return

        # TODO:
        # 1. Convert ROS Image to PIL/CV image
        # 2. Resize to model_params['image_size']
        # 3. Build image history
        # 4. Convert relative goal to:
        #    [dx/0.25, dy/0.25, cos(dtheta), sin(dtheta)]
        # 5. Call model(...)
        # 6. Convert waypoints to linear/angular velocity

        # Placeholder command for testing
        cmd = Twist()
        cmd.linear.x = 0.1
        cmd.angular.z = 0.0

        self.cmd_pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = LogoNavInferenceNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()