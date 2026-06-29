from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
	return LaunchDescription([
		Node(
			package='video_logger',
			executable='dashboard_node',
			name='dashboard_node',
			output='screen',
		),
	])
