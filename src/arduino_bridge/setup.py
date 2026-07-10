from setuptools import setup

package_name = 'arduino_bridge'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='zhangboya',
    maintainer_email='zhangboya@example.com',
    description='ROS2 bridge that forwards motor commands to Arduino over USB serial.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'arduino_bridge_node = arduino_bridge.arduino_bridge_node:main',
        ],
    },
)
