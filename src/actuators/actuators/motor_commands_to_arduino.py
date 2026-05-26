import serial

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray


class MotorCommandsToArduino(Node):
    def __init__(self):
        super().__init__("motor_commands_to_arduino")

        self.declare_parameter("serial_port", "/dev/ttyACM0")
        self.declare_parameter("baudrate", 115200)
        self.declare_parameter("topic", "/motion/motor_commands")
        self.declare_parameter("velocity_scale", 1000.0)
        self.declare_parameter("angle_scale", 1000.0)

        serial_port = self.get_parameter("serial_port").get_parameter_value().string_value
        baudrate = self.get_parameter("baudrate").get_parameter_value().integer_value
        topic = self.get_parameter("topic").get_parameter_value().string_value
        self.velocity_scale = (
            self.get_parameter("velocity_scale").get_parameter_value().double_value
        )
        self.angle_scale = self.get_parameter("angle_scale").get_parameter_value().double_value

        self.serial_connection = serial.Serial(serial_port, baudrate, timeout=1)
        self.subscription = self.create_subscription(
            Float32MultiArray,
            topic,
            self.listener_callback,
            10,
        )

        self.get_logger().info(
            f"Forwarding {topic} to Arduino on {serial_port} @ {baudrate} baud "
            f"(velocity_scale={self.velocity_scale}, angle_scale={self.angle_scale})"
        )

    def listener_callback(self, msg: Float32MultiArray) -> None:
        if len(msg.data) % 2 != 0:
            self.get_logger().warning(
                "Received motor command array with an odd number of elements; expected velocity/angle pairs."
            )
            return

        scaled_values = []
        for index, value in enumerate(msg.data):
            scale = self.velocity_scale if index % 2 == 0 else self.angle_scale
            scaled_values.append(str(int(round(value * scale))))

        # Format: M,<vel0_i>,<ang0_i>,...,<velN_i>,<angN_i>\n
        packet = "M," + ",".join(scaled_values) + "\n"
        self.serial_connection.write(packet.encode("utf-8"))

    def destroy_node(self):
        if hasattr(self, "serial_connection") and self.serial_connection.is_open:
            self.serial_connection.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MotorCommandsToArduino()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
