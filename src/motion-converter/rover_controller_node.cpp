#include <cmath>
#include <memory>
#include <mutex>

#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/float32.hpp>
#include <std_msgs/msg/string.hpp>

class RoverControllerNode : public rclcpp::Node {
public:
  RoverControllerNode() : Node("rover_controller_node") {
    yaw_tolerance_deg_ = declare_parameter<double>("yaw_tolerance_deg", yaw_tolerance_deg_);
    turn_speed_rad_s_ = declare_parameter<double>("turn_speed_rad_s", turn_speed_rad_s_);

    if (yaw_tolerance_deg_ < 0.0) {
      RCLCPP_WARN(get_logger(), "Parameter yaw_tolerance_deg is negative (%.3f). Using absolute value.",
                  yaw_tolerance_deg_);
      yaw_tolerance_deg_ = std::abs(yaw_tolerance_deg_);
    }
    if (turn_speed_rad_s_ < 0.0) {
      RCLCPP_WARN(get_logger(), "Parameter turn_speed_rad_s is negative (%.3f). Using absolute value.",
                  turn_speed_rad_s_);
      turn_speed_rad_s_ = std::abs(turn_speed_rad_s_);
    }

    RCLCPP_INFO(get_logger(), "Using parameters: yaw_tolerance_deg=%.3f, turn_speed_rad_s=%.3f",
                yaw_tolerance_deg_, turn_speed_rad_s_);

    cmd_vel_sub_ = create_subscription<geometry_msgs::msg::Twist>(
        "/mbra/cmd_vel", 10,
        std::bind(&RoverControllerNode::cmdVelCallback, this, std::placeholders::_1));

    stop_sub_ = create_subscription<std_msgs::msg::String>(
        "/actions/stop", 10,
        std::bind(&RoverControllerNode::stopCallback, this, std::placeholders::_1));

    turn_sub_ = create_subscription<std_msgs::msg::Float32>(
        "/actions/turn", 10,
        std::bind(&RoverControllerNode::turnCallback, this, std::placeholders::_1));

    mbra_enable_sub_ = create_subscription<std_msgs::msg::Bool>(
        "/actions/enable_mbra", 10,
        std::bind(&RoverControllerNode::mbraEnableCallback, this, std::placeholders::_1));

    pose_sub_ = create_subscription<geometry_msgs::msg::PoseStamped>(
        "/robot/pose", 10,
        std::bind(&RoverControllerNode::poseCallback, this, std::placeholders::_1));

    publisher_ = create_publisher<geometry_msgs::msg::Twist>("/motion/cmd_vel", 10);

    // Keep publishing/turn-control in a timer instead of blocking inside callbacks.
    control_timer_ = create_wall_timer(
        std::chrono::milliseconds(20),
        std::bind(&RoverControllerNode::controlLoop, this));
  }

private:
  static double normalizeDeg(double angle_deg) {
    while (angle_deg <= -180.0) {
      angle_deg += 360.0;
    }
    while (angle_deg > 180.0) {
      angle_deg -= 360.0;
    }
    return angle_deg;
  }

  static double shortestAngleErrorDeg(double target_deg, double current_deg) {
    return normalizeDeg(target_deg - current_deg);
  }

  void cmdVelCallback(const geometry_msgs::msg::Twist::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);
    mbra_linear_ = msg->linear.x;
    mbra_angular_ = msg->angular.z;
    RCLCPP_INFO(get_logger(), "Received cmd_vel: linear_x=%.3f, angular_z=%.3f", mbra_linear_,
                mbra_angular_);
  }

  void stopCallback(const std_msgs::msg::String::SharedPtr /*msg*/) {
    std::lock_guard<std::mutex> lock(mutex_);
    action_linear_ = 0.0;
    action_angular_ = 0.0;
    turning_active_ = false;
    RCLCPP_INFO(get_logger(), "Received stop command, stopping the rover.");
  }

  void turnCallback(const std_msgs::msg::Float32::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);

    const double turn_angle_deg = static_cast<double>(msg->data);
    target_yaw_deg_ = normalizeDeg(yaw_deg_ + turn_angle_deg);

    turning_active_ = true;
    RCLCPP_INFO(get_logger(), "Received turn command: turn_angle=%.2f deg, target_yaw=%.2f deg",
                turn_angle_deg, target_yaw_deg_);
  }

  void mbraEnableCallback(const std_msgs::msg::Bool::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);
    mbra_enabled_ = msg->data;
    RCLCPP_INFO(get_logger(), "MBRA enabled: %s", mbra_enabled_ ? "true" : "false");
  }

  void poseCallback(const geometry_msgs::msg::PoseStamped::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);

    // Convert quaternion to yaw (Z axis rotation).
    const auto &q = msg->pose.orientation;
    const double siny_cosp = 2.0 * (q.w * q.z + q.x * q.y);
    const double cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z);
    const double yaw_rad = std::atan2(siny_cosp, cosy_cosp);

    yaw_deg_ = normalizeDeg(yaw_rad * 180.0 / M_PI);
    RCLCPP_INFO(get_logger(), "Received pose: yaw=%.2f deg", yaw_deg_);
  }

  void controlLoop() {
    std::lock_guard<std::mutex> lock(mutex_);

    if (turning_active_) {
      const double error_deg = shortestAngleErrorDeg(target_yaw_deg_, yaw_deg_);

      if (std::abs(error_deg) <= yaw_tolerance_deg_) {
        action_angular_ = 0.0;
        turning_active_ = false;
      } else {
        action_angular_ = (error_deg > 0.0) ? turn_speed_rad_s_ : -turn_speed_rad_s_;
      }
    }

    geometry_msgs::msg::Twist cmd;
    if (mbra_enabled_) {
      cmd.linear.x = mbra_linear_;
      cmd.angular.z = mbra_angular_;
    } else {
      cmd.linear.x = action_linear_;
      cmd.angular.z = action_angular_;
    }

    publisher_->publish(cmd);
  }

  std::mutex mutex_;

  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_sub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr stop_sub_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr turn_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr mbra_enable_sub_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr pose_sub_;

  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr publisher_;
  rclcpp::TimerBase::SharedPtr control_timer_;

  double mbra_linear_ = 0.0;
  double mbra_angular_ = 0.0;
  bool mbra_enabled_ = false;

  double action_linear_ = 0.0;
  double action_angular_ = 0.0;

  double yaw_deg_ = 0.0;
  double target_yaw_deg_ = 0.0;
  bool turning_active_ = false;

  double yaw_tolerance_deg_ = 5.0;
  double turn_speed_rad_s_ = 0.5;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<RoverControllerNode>());
  rclcpp::shutdown();
  return 0;
}
