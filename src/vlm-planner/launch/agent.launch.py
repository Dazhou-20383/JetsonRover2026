from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
	return LaunchDescription([
		Node(
			package='vlm-planner',
			executable='vlm_node',
			name='vlm_node',
			output='screen',
		),
		Node(
			package='vlm-planner',
			executable='action_server',
			name='action_server',
			output='screen',
		),
	])
