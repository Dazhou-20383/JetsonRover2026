#!/usr/bin/env python3

"""Send one example motor command over serial.

This mirrors the Arduino bridge node wire format:
comma-separated floating point values, newline terminated.
For 6 wheels, the payload contains 12 values in the form
[speed, angle, speed, angle, ...].
"""

from __future__ import annotations

import argparse

try:
	import serial
except ImportError:
	serial = None


EXAMPLE_PAYLOAD = [
	0.60, 30.00,
	0.00, 0.00,
	0.00, 0.00,
	0.00, 0.00,
	0.00, 0.00,
	0.00, 0.00,
]


def build_message(values: list[float]) -> str:
	if len(values) != 12:
		raise ValueError('expected a 12-value payload for 6 wheels')

	return ','.join(f'{value:.6f}' for value in values) + '\n'


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description='Send one serial motor command')
	parser.add_argument('--port', default='/dev/ttyACM0', help='Serial port path')
	parser.add_argument('--baudrate', type=int, default=115200, help='Serial baudrate')
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	message = build_message(EXAMPLE_PAYLOAD)

	if serial is None:
		raise SystemExit('pyserial is required: pip install pyserial')

	with serial.Serial(args.port, args.baudrate, timeout=1) as connection:
		connection.write(message.encode('utf-8'))
		connection.flush()
		print(f'sent to {args.port}: {message.strip()}')


if __name__ == '__main__':
	main()
