from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='mbra',
            executable='logonav_node',
            name='logonav_node',
            output='screen',
        ),
        Node(
            package='mbra',
            executable='cmd_vel_relay_node',
            name='cmd_vel_relay_node',
            output='screen',
        ),
        Node(
            package='motion_converter',
            executable='motion_converter_node',
            name='motion_converter_node',
            output='screen',
        ),
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
        Node(
            package='arduino_bridge',
            executable='arduino_bridge_node',
            name='arduino_bridge_node',
            output='screen',
        ),
    ])
