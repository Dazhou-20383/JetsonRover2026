from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='motion_converter',
            executable='motion_converter_node',
            name='motion_converter_node',
            output='screen',
        ),
        Node(
            package='manuel_controller',
            executable='manuel_controller_node',
            name='manuel_controller_node',
            output='screen',
        )
    ])