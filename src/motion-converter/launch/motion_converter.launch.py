from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params_file = LaunchConfiguration('params_file')

    default_params_file = PathJoinSubstitution(
        [FindPackageShare('motion_converter'), 'config', 'rover_controller_params.yaml']
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params_file,
            description='Path to the rover controller ROS2 parameters file',
        ),
        Node(
            package='motion_converter',
            executable='motion_converter_node',
            name='motion_converter_node',
            output='screen',
        ),
        Node(
            package='motion_converter',
            executable='rover_controller_node',
            name='rover_controller_node',
            output='screen',
            parameters=[params_file],
        ),
    ])
