from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'mbra'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('mbra/train/config/*.yaml')),
        (os.path.join('share', package_name, 'model_weights'), glob('model_weights/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='boya',
    maintainer_email='kevin20383sabis@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'logonav_node = mbra.deployment.LogoNav_ros:main',
            'cmd_vel_relay_node = mbra.cmd_vel_relay_node:main',
            'test_goal_node = mbra.test.manual_goal_test:main'
        ],
    },
)
