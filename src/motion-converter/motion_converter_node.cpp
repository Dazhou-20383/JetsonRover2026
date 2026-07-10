#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <std_msgs/msg/float32_multi_array.hpp>

#include <cmath>
#include <memory>
#include <vector>

struct Wheel {
    double x;
    double y;
    double velocity;
    double steering_angle;
};

class MotionConverter : public rclcpp::Node {
public:
    MotionConverter() : Node("motion_converter_node") {
        subscriber_ = create_subscription<geometry_msgs::msg::Twist>(
                "/motion/cmd_vel", 10,
                std::bind(&MotionConverter::cmdVelCallback, this, std::placeholders::_1));

        publisher_ = create_publisher<std_msgs::msg::Float32MultiArray>("/motion/motor_commands", 10);

        wheels_ = {
                {0.4, 0.3, 0.0, 0.0},    // Front Left
                {0.4, -0.3, 0.0, 0.0},   // Front Right
                {0.0, 0.3, 0.0, 0.0},    // Middle Left
                {0.0, -0.3, 0.0, 0.0},   // Middle Right
                {-0.15, 0.3, 0.0, 0.0},   // Rear Left
                {-0.15, -0.3, 0.0, 0.0},  // Rear Right
        };
    }

private:
    void cmdVelCallback(const geometry_msgs::msg::Twist::SharedPtr msg) {
        std_msgs::msg::Float32MultiArray motor_commands;
        motor_commands.data.reserve(wheels_.size() * 2);

        constexpr double kPi = 3.14159265358979323846;

        for (auto &w : wheels_) {
            const double vx = msg->linear.x - w.y * msg->angular.z;
            const double vy = msg->linear.y + w.x * msg->angular.z;

            double steering_angle_deg = std::atan2(vy, vx) * 180.0 / kPi;
            double wheel_speed = std::hypot(vx, vy);

            if (steering_angle_deg > 90.0) {
                steering_angle_deg -= 180.0;
                wheel_speed = -wheel_speed;
            } else if (steering_angle_deg < -90.0) {
                steering_angle_deg += 180.0;
                wheel_speed = -wheel_speed;
            }

            w.velocity = wheel_speed;
            w.steering_angle = steering_angle_deg;

            motor_commands.data.push_back(static_cast<float>(w.velocity));
            motor_commands.data.push_back(static_cast<float>(w.steering_angle));
        }

        publisher_->publish(motor_commands);
    }

    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr subscriber_;
    rclcpp::Publisher<std_msgs::msg::Float32MultiArray>::SharedPtr publisher_;
    std::vector<Wheel> wheels_;
};

int main(int argc, char *argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<MotionConverter>());
    rclcpp::shutdown();
    return 0;
}