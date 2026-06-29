import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
	return LaunchDescription([
		IncludeLaunchDescription(
			PythonLaunchDescriptionSource(
				os.path.join(
					get_package_share_directory('motion_converter'),
					'launch',
					'motion_converter.launch.py',
				)
			)
		),
		IncludeLaunchDescription(
			PythonLaunchDescriptionSource(
				os.path.join(
					get_package_share_directory('sensors'),
					'launch',
					'sensors.launch.py',
				)
			)
		),
		IncludeLaunchDescription(
			PythonLaunchDescriptionSource(
				os.path.join(
					get_package_share_directory('vlm-planner'),
					'launch',
					'agent.launch.py',
				)
			)
		),
		Node(
			package='video-logger',
			executable='dashboard_node',
			name='dashboard_node',
			output='screen',
		),
	])
