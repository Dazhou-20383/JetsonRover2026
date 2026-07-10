colcon build
source install/setup.bash
python3 wake.py &
ros2 launch manuel.launch.py