import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import serial

class CmdVelToArduino(Node):
    def __init__(self):
        super().__init__('cmd_vel_to_arduino')
        # Initialize serial communication matching your Arduino configuration
        self.ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
        self.subscription = self.create_subscription(
            Twist,
            'cmd_vel',
            self.listener_callback,
            10)

    def listener_callback(self, msg):
        linear_x = msg.linear.x
        angular_z = msg.angular.z
        
        # Package data into a simple string formatted packet (e.g., "v1.2,w0.5\n")
        packet = f"v{linear_x:.2f},w{angular_z:.2f}\n"
        self.ser.write(packet.encode('utf-8')) # Send over USB

def main(args=None):
    rclpy.init(args=args)
    node = CmdVelToArduino()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
