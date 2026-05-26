from rclpy import Node
import rclpy
from geometry_msgs.msg import Twist, PoseStamped
from std_msgs.msg import String, Float32, Bool
import time

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

        self.pose_sub = self.create_subscription(PoseStamped, '/robot/pose', self.pose_callback, 10)
        self.yaw = 0.0

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
           Calculate the target orientation from turn angle in degrees
           Set angular velocity until pose enter desired range"""
        turn_angle = msg.data
        target_yaw = (self.yaw + turn_angle) % 360
        tolerance = 5.0  # degrees
        turn_speed = 0.5  # radians per second
        self.get_logger().info(f"Received turn command: turn_angle={turn_angle}, target_yaw={target_yaw}")
        while self.yaw < target_yaw - tolerance or self.yaw > target_yaw + tolerance:
            self.action_angular = turn_speed if (target_yaw - self.yaw) > 0 else -turn_speed
            time.sleep(0.01)
        # Polling while the rover is turning

    def mbra_enable_callback(self, msg):
        self.mbra_enabled = msg.data
        self.get_logger().info(f"MBRA enabled: {self.mbra_enabled}")


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

    def pose_callback(self, msg):
        self.yaw = msg.pose.orientation.z
        self.get_logger().info(f"Received pose: yaw={self.yaw}")