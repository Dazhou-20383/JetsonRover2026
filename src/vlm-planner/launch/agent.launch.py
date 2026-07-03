from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
	return LaunchDescription([
		DeclareLaunchArgument(
			'ollama_server_ip',
			default_value='localhost',
			description='Ollama server IP address',
		),
		SetEnvironmentVariable(
			name='OLLAMA_SERVER_IP',
			value=LaunchConfiguration('ollama_server_ip'),
		),
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
