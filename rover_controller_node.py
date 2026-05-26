from rclpy import Node
import rclpy
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Float32, Bool


class RoverControllerNode(Node):
    def __init__(self):
        super().__init__('rover_controller_node')
        self.subscription = self.create_subscription(
            Twist,
            '/mbra/cmd_vel',
            self.cmd_vel_callback,
            10
        )

        self.stop_service = self.create_subscription(
            String,
            '/actions/stop',
            self.stop_callback
        )
        self.turn_service = self.create_subscription(
            Float32,
            '/actions/turn',
            self.turn_callback
        )
        self.mbra_services = self.create_subscription(
            Bool,
            '/actions/enable_mbra',
            self.mbra_enable_callback
        )

        self.mbra_linear = 0.0
        self.mbra_angular = 0.0

        self.mbra_enabled = False

        self.action_linear = 0.0
        self.action_angular = 0.0

        self.publisher = self.create_publisher(Twist, '/motion/cmd_vel', 10)

        self.pose_sub = self.create_subscription(

    def cmd_vel_callback(self, msg):
        self.mbra_linear = msg.linear.x
        self.mbra_angular = msg.angular.z
        self.get_logger().info(f"Received cmd_vel: linear_x={self.mbra_linear}, angular_z={self.mbra_angular}")
        
    def stop_callback(self, msg):
        """Disable mbra and stop rover immediately."""
        self.action_linear = 0.0
        self.action_angular = 0.0
        self.get_logger().info("Received stop command, stopping the rover.")

    def turn_callback(self, msg):
        """Disable mbra and log the current orientation.
           Calculate the target orientation.
           Set angular velocity until pose enter desired range"""
        

    def mbra_enable_callback(self, msg):
        pass

    def publish_motion_command(self):
        cmd = Twist()
        if self.mbra_enabled:
            cmd.linear.x = self.mbra_linear 
            cmd.angular.z = self.mbra_angular
        else:
            cmd.linear.x = self.action_linear
            cmd.angular.z = self.action_angular

        self.publisher.publish(cmd)
        self.get_logger().info(f"Published motion command: linear_x={cmd.linear.x}, angular_z={cmd.angular.z}")