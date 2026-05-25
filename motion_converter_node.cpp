#include <rclcpp/rcl_cpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <std_msgs/msg/Float32MultiArray.hpp>

#include <vector>
#include <cmath>

typedef struct Wheel{
    double x;
    double y;
    double velocity;
    double steering_angle;
}

std::vector<Wheel> wheels = {
    {0.5, 0.5, 0.0, 0.0},   // Front Left
    {0.5, -0.5, 0.0, 0.0},  // Front Right
    {0, 0, 0.0, 0.0},       // Middle Left
    {0, 0, 0.0, 0.0},       // Middle Right
    {-0.5, 0.5, 0.0, 0.0},  // Rear Left
    {-0.5, -0.5, 0.0, 0.0}  // Rear Right
};

class MotionConverter: public rclcpp::Node
{
public:
    MotionConverter()
    :Node("motion_converter_node")
    {
        // Initialize ROS2 node and publisher
        rclcpp::Node::SharedPtr node = rclcpp::Node::make_shared("motion_converter_node");
        subscriber_ = node->create_subscription<geometry_msgs::msg::Twist>(
            "/motion/cmd_vel", 10, std::bind(&MotionConverter::mbra_callback, this, std::placeholders::_1));

        publisher_ = node->create_publisher<std_msgs:msg::Float32MultiArray>(
            "/motion/motor_commands", 10
        )

    }

private:
    void mbra_callback(const geometry_msgs::msg::Twist::SharedPtr msg)
    {
        std_msgs::msg::Float32MultiArray motor_commands;

        for(wheel* w : wheels)
        {
            double vx = msg->linear.x - w.y * msg->angular.z;
            double vy = msg->linear.y + w.x * msg->angular.z;

            w->velocity = std::sqrt(vx * vx + vy * vy);
            w->steering_angle = std::atan2(vy, vx);

            motor_commands.data.push_back(w.velocity);
            motor_commands.data.push_back(w.steering_angle);
        }
    }

    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr subscriber_;
    rclcpp::Publisher<std_msgs::msg::Float32MultiArray>::SharedPtr publisher_;
};