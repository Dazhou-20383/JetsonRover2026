from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# cli argument like ros2 launch arduino_bridge arduino_bridge.launch.py serial_port:=/dev/ttyACM0 baudrate:=115200 serial_timeout_sec:=0.1 topic_name:=/motion/motor_commands
def generate_launch_description():
    serial_port = LaunchConfiguration('serial_port')
    baudrate = LaunchConfiguration('baudrate')
    serial_timeout = LaunchConfiguration('serial_timeout_sec')
    topic_name = LaunchConfiguration('topic_name')

    return LaunchDescription([
        DeclareLaunchArgument('serial_port', default_value='/dev/ttyAMA0'),
        DeclareLaunchArgument('baudrate', default_value='115200'),
        DeclareLaunchArgument('serial_timeout_sec', default_value='0.1'),
        DeclareLaunchArgument('topic_name', default_value='/motion/motor_commands'),

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
        ),

        Node(
            package='arduino_bridge',
            executable='arduino_bridge_node',
            name='arduino_bridge_node',
            output='screen',
            parameters=[{
                'serial_port': serial_port,
                'baudrate': baudrate,
                'serial_timeout_sec': serial_timeout,
                'topic_name': topic_name,
            }]
        ),
    ])
