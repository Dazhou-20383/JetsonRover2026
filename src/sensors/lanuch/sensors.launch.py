from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
	return LaunchDescription([
		Node(
			package='sensors',
			executable='camera_node',
			name='camera_node',
			output='screen',
		),
		Node(
			package='sensors',
			executable='iphone_pose_node',
			name='iphone_pose_node',
			output='screen',
		),
	])
