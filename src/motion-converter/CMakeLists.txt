cmake_minimum_required(VERSION 3.8)
project(motion_converter)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(action_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)

add_executable(motion_converter_node motion_converter_node.cpp)
ament_target_dependencies(motion_converter_node
  rclcpp
  geometry_msgs
  std_msgs
)

add_executable(rover_controller_node rover_controller_node.cpp)
ament_target_dependencies(rover_controller_node
  action_msgs
  rclcpp
  geometry_msgs
  std_msgs
)

install(TARGETS
  motion_converter_node
  rover_controller_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY config
  DESTINATION share/${PROJECT_NAME}
)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
