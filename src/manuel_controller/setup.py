from setuptools import setup

package_name = 'manuel_controller'

setup(
	name=package_name,
	version='0.0.1',
	packages=[package_name],
	data_files=[
		('share/ament_index/resource_index/packages', ['resource/' + package_name]),
		('share/' + package_name, ['package.xml']),
	],
	install_requires=['setuptools', 'websockets'],
	zip_safe=True,
	maintainer='zhangboya',
	maintainer_email='zhangboya@example.com',
	description='ROS2 manual controller that publishes cmd_vel from WebSocket joystick input.',
	license='Apache-2.0',
	tests_require=['pytest'],
	entry_points={
		'console_scripts': [
			'manuel_controller_node = manuel_controller.manuel_controller_node:main',
		],
	},
)
