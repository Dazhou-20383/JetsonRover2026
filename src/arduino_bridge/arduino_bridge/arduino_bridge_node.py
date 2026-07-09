#!/usr/bin/env python3

import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
import serial

class ArduinoBridgeNode(Node):
	def __init__(self) -> None:
		super().__init__('arduino_bridge_node')

		self.declare_parameter('serial_port', '/dev/ttyAMA0')
		self.declare_parameter('baudrate', 115200)
		self.declare_parameter('serial_timeout_sec', 0.1)
		self.declare_parameter('topic_name', '/motion/motor_commands')

		self._serial_port = self.get_parameter('serial_port').value
		self._baudrate = int(self.get_parameter('baudrate').value)
		self._serial_timeout = float(self.get_parameter('serial_timeout_sec').value)
		self._topic_name = self.get_parameter('topic_name').value

		self._serial = None
		self._connect_serial()

		self._read_thread_stop = threading.Event()
		self._read_thread = threading.Thread(
			target=self._read_serial_loop,
			daemon=True,
		)
		self._read_thread.start()

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
		except Exception as exc:
			self._serial = None
			self.get_logger().error(
				f'Failed to open serial port {self._serial_port}: {exc}'
			)

	def _read_serial_loop(self) -> None:
		"""Continuously read lines from the Arduino and log them.

		This gives visibility into the Arduino's echo-back (OK: ...) and
		error (ERR: ...) messages, so serial issues show up in the ROS
		log instead of being silently dropped.
		"""
		while not self._read_thread_stop.is_set():
			if self._serial is None or not self._serial.is_open:
				# Not connected yet (or connection failed) -- avoid a busy
				# loop while we wait for _connect_serial to succeed.
				self._read_thread_stop.wait(timeout=1.0)
				continue

			try:
				line = self._serial.readline()
			except Exception as exc:
				self.get_logger().error(f'Serial read failed: {exc}')
				self._read_thread_stop.wait(timeout=1.0)
				continue

			if not line:
				# readline() timed out with no data; loop again.
				continue

			decoded = line.decode('utf-8', errors='replace').rstrip('\r\n')
			if not decoded:
				continue

			if decoded.startswith('ERR'):
				self.get_logger().warn(f'Arduino: {decoded}')
			else:
				self.get_logger().info(f'Arduino: {decoded}')

	def _motor_commands_callback(self, msg: Float32MultiArray) -> None:
		if self._serial is None:
			return

		# Send CSV + newline so Arduino can parse one command per line.
		payload = ','.join(f'{value:.6f}' for value in msg.data) + '\n'

		try:
			self._serial.write(payload.encode('utf-8'))
			self._serial.flush()
		except Exception as exc:
			self.get_logger().error(f'Serial write failed: {exc}')

	def destroy_node(self) -> bool:
		self._read_thread_stop.set()
		if self._read_thread.is_alive():
			self._read_thread.join(timeout=2.0)
		if self._serial is not None and self._serial.is_open:
			self._serial.close()
		return super().destroy_node()


def main(args=None) -> None:
	rclpy.init(args=args)
	node = ArduinoBridgeNode()

	try:
		rclpy.spin(node)
	except KeyboardInterrupt:
		pass
	finally:
		node.destroy_node()
		rclpy.shutdown()


if __name__ == '__main__':
	main()