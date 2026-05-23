import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from agent import VLMAgent

class VLMNode(Node):
    def __init__(self):
        super().__init__('vlm_node')
        self.get_logger().info('VLM Node has been started.')

        self.action_publisher = self.create_publisher(String, '/rover/actions', 10)

        # run agent decision loop every 5 seconds
        self.timer = self.create_timer(5.0, self.run_agent)

        self.instruction_sub = self.create_subscription()
        self.pose_sub = self.create_subscription()
        self.observation_sub = self.create_subscription()

        self.agent = VLMAgent(self)

    def instruction_callback(self, msg):
        # TODO: split instruction into distance, direction, and landmark
        self.get_logger().info(f'Received instruction: {msg.data}')
        self.agent.instruction = msg.data
    
    def pose_callback(self, msg):
        self.get_logger().info(f'Received pose: {msg.data}')
        self.agent.pose = msg.data

    def observation_callback(self, msg):
        self.get_logger().info(f'Received observation: {msg.data}')
        self.agent.observation = msg.data

    def run_agent(self):
        action = self.agent.decide_action()
        if action:
            self.get_logger().info(f'Publishing action: {action}')
            self.action_publisher.publish(String(data=action))

    


def main(args=None):
    rclpy.init(args=args)
    node = VLMNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

if __name__ == '__main__':
    main()
