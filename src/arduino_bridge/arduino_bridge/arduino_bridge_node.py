#!/usr/bin/env python3

import signal

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray

try:
	import serial
except ImportError:
	serial = None


class ArduinoBridgeNode(Node):
	def __init__(self) -> None:
		super().__init__('arduino_bridge_node')

		self.declare_parameter('serial_port', '/dev/ttyACM0')
		self.declare_parameter('baudrate', 115200)
		self.declare_parameter('serial_timeout_sec', 0.1)
		self.declare_parameter('topic_name', '/motion/motor_commands')

		self._serial_port = self.get_parameter('serial_port').value
		self._baudrate = int(self.get_parameter('baudrate').value)
		self._serial_timeout = float(self.get_parameter('serial_timeout_sec').value)
		self._topic_name = self.get_parameter('topic_name').value

		self._serial = None
		self._connect_serial()

		self._subscription = self.create_subscription(
			Float32MultiArray,
			self._topic_name,
			self._motor_commands_callback,
			10,
		)

		self.get_logger().info(
			f'Listening on {self._topic_name} and forwarding to '
			f'{self._serial_port} @ {self._baudrate} baud'
		)

	def _connect_serial(self) -> None:
		if serial is None:
			self.get_logger().error(
				'pyserial is not installed. Install it to enable USB serial output.'
			)
			return

		try:
			self._serial = serial.Serial(
				port=self._serial_port,
				baudrate=self._baudrate,
				timeout=self._serial_timeout,
			)
			self.get_logger().info(f'Connected to Arduino on {self._serial_port}')
		except serial.SerialException as exc:
			self._serial = None
			self.get_logger().error(
				f'Failed to open serial port {self._serial_port}: {exc}'
			)

	def _motor_commands_callback(self, msg: Float32MultiArray) -> None:
		if self._serial is None:
			return

		# Send CSV + newline so Arduino can parse one command per line.
		payload = ','.join(f'{value:.6f}' for value in msg.data) + '\n'

		try:
			self._serial.write(payload.encode('utf-8'))
			self._serial.flush()
		except serial.SerialException as exc:
			self.get_logger().error(f'Serial write failed: {exc}')

	def destroy_node(self) -> bool:
		if self._serial is not None and self._serial.is_open:
			self._serial.close()
		return super().destroy_node()


def _install_shutdown_handlers(node):
	def _handle_shutdown(signum, frame):
		if rclpy.ok():
			node.get_logger().info(f'Received signal {signum}, shutting down.')
			rclpy.try_shutdown()

	signal.signal(signal.SIGINT, _handle_shutdown)
	if hasattr(signal, 'SIGTERM'):
		signal.signal(signal.SIGTERM, _handle_shutdown)


def main(args=None) -> None:
	rclpy.init(args=args)
	node = ArduinoBridgeNode()
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
