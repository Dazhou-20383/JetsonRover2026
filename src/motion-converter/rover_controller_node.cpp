#include <cmath>
#include <memory>
#include <mutex>

#include <std_msgs/msg/bool.hpp>
#include <geometry_msgs/msg/pose2_d.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <rclcpp/rclcpp.hpp>
#include <action_msgs/srv/enable_mbra_srv.hpp>
#include <action_msgs/srv/stop_srv.hpp>
#include <action_msgs/srv/turn_srv.hpp>

class RoverControllerNode : public rclcpp::Node {
public:
  RoverControllerNode() : Node("rover_controller_node") {
    yaw_tolerance_deg_ = declare_parameter<double>("yaw_tolerance_deg", yaw_tolerance_deg_);
    turn_speed_deg_s_ = declare_parameter<double>("turn_speed_deg_s", turn_speed_deg_s_);

    if (yaw_tolerance_deg_ < 0.0) {
      RCLCPP_WARN(get_logger(), "Parameter yaw_tolerance_deg is negative (%.3f). Using absolute value.",
                  yaw_tolerance_deg_);
      yaw_tolerance_deg_ = std::abs(yaw_tolerance_deg_);
    }
    if (turn_speed_deg_s_ < 0.0) {
      RCLCPP_WARN(get_logger(), "Parameter turn_speed_deg_s is negative (%.3f). Using absolute value.",
                  turn_speed_deg_s_);
      turn_speed_deg_s_ = std::abs(turn_speed_deg_s_);
    }

    RCLCPP_INFO(get_logger(), "Using parameters: yaw_tolerance_deg=%.3f, turn_speed_deg_s=%.3f",
                yaw_tolerance_deg_, turn_speed_deg_s_);

    cmd_vel_sub_ = create_subscription<geometry_msgs::msg::Twist>(
        "/mbra/cmd_vel", 10,
        std::bind(&RoverControllerNode::cmdVelCallback, this, std::placeholders::_1));

    stop_srv_ = create_service<action_msgs::srv::StopSrv>(
      "/actions/stop",
      std::bind(&RoverControllerNode::stopCallback, this, std::placeholders::_1,
            std::placeholders::_2));

    turn_srv_ = create_service<action_msgs::srv::TurnSrv>(
      "/actions/turn",
      std::bind(&RoverControllerNode::turnCallback, this, std::placeholders::_1,
            std::placeholders::_2));

    mbra_enable_srv_ = create_service<action_msgs::srv::EnableMBRASrv>(
      "/actions/enable_mbra",
      std::bind(&RoverControllerNode::mbraEnableCallback, this, std::placeholders::_1,
            std::placeholders::_2));

    pose_sub_ = create_subscription<geometry_msgs::msg::Pose2D>(
        "/robot/pose", 10,
        std::bind(&RoverControllerNode::poseCallback, this, std::placeholders::_1));

    publisher_ = create_publisher<geometry_msgs::msg::Twist>("/motion/cmd_vel", 10);

    mbra_enable_pub_ = create_publisher<std_msgs::msg::Bool>(
        "/mbra/enable", 10);
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
  }

  void stopCallback(const std::shared_ptr<action_msgs::srv::StopSrv::Request> /*request*/,
                    std::shared_ptr<action_msgs::srv::StopSrv::Response> response) {
    std::lock_guard<std::mutex> lock(mutex_);
    action_linear_ = 0.0;
    action_angular_ = 0.0;
    turning_active_ = false;
    response->success = true;
    response->error.clear();
    RCLCPP_INFO(get_logger(), "Received stop command, stopping the rover.");
  }

  void turnCallback(const std::shared_ptr<action_msgs::srv::TurnSrv::Request> request,
                    std::shared_ptr<action_msgs::srv::TurnSrv::Response> response) {
    std::lock_guard<std::mutex> lock(mutex_);

    target_yaw_deg_ = normalizeDeg(static_cast<double>(request->orientation));

    turning_active_ = true;
    response->success = true;
    response->error.clear();
    RCLCPP_INFO(get_logger(), "Received turn command: target_yaw=%.2f deg", target_yaw_deg_);
  }

  void mbraEnableCallback(const std::shared_ptr<action_msgs::srv::EnableMBRASrv::Request> request,
                          std::shared_ptr<action_msgs::srv::EnableMBRASrv::Response> response) {
    std::lock_guard<std::mutex> lock(mutex_);
    mbra_enabled_ = request->enable;
    response->success = true;
    response->error.clear();
    std_msgs::msg::Bool enable_msg;
    enable_msg.data = mbra_enabled_;
    mbra_enable_pub_->publish(enable_msg);
    RCLCPP_INFO(get_logger(), "MBRA enabled: %s", mbra_enabled_ ? "true" : "false");
  }

  void poseCallback(const geometry_msgs::msg::Pose2D::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(mutex_);

    yaw_deg_ = normalizeDeg(msg->theta);
  }

  void controlLoop() {
    std::lock_guard<std::mutex> lock(mutex_);

    if (turning_active_) {
      const double error_deg = shortestAngleErrorDeg(target_yaw_deg_, yaw_deg_);

      if (std::abs(error_deg) <= yaw_tolerance_deg_) {
        action_angular_ = 0.0;
        turning_active_ = false;
      } else {
        action_angular_ = (error_deg > 0.0) ? turn_speed_deg_s_ : -turn_speed_deg_s_;
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
  rclcpp::Service<action_msgs::srv::StopSrv>::SharedPtr stop_srv_;
  rclcpp::Service<action_msgs::srv::TurnSrv>::SharedPtr turn_srv_;
  rclcpp::Service<action_msgs::srv::EnableMBRASrv>::SharedPtr mbra_enable_srv_;
  rclcpp::Subscription<geometry_msgs::msg::Pose2D>::SharedPtr pose_sub_;
  
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr mbra_enable_pub_;
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
  double turn_speed_deg_s_ = 0.5;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<RoverControllerNode>());
  rclcpp::shutdown();
  return 0;
}
