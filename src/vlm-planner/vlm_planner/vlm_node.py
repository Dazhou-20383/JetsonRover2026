import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Pose2D
from sensor_msgs.msg import Image
from action_msgs.srv import Tool
import json
import collections

from .agent import VLMAgent
from .client import OllamaClient

from .tools import tools

class VLMNode(Node):
    def __init__(self):
        super().__init__('vlm_node')
        self.get_logger().info('VLM Node has been started.')

        self.action_client = self.create_client(Tool, '/actions')
        self.max_tool_iterations = 4

        # run agent decision loop every 5 seconds
        self.timer = self.create_timer(5.0, self.run_agent)

        self.instruction_sub = self.create_subscription(String, '/robot/directions', self.instruction_callback, 10)
        self.pose_sub = self.create_subscription(Pose2D, '/robot/pose', self.pose_callback, 10)
        self.observation_sub = self.create_subscription(Image, '/camera/image_raw', self.observation_callback, 10)

        vlm_client = OllamaClient(tools=tools, max_tokens=512)

        self.agent = VLMAgent(vlm_client)
        self.current_state = {
            'instruction': '',
            'current_pose': '',
            'current_waypoint': '',
            'current_observation': '',
            'history': collections.deque(maxlen=2),
        }

    def instruction_callback(self, msg):
        # TODO: split instruction into distance, direction, and landmark
        self.get_logger().info(f'Received instruction: {msg.data}')
        self.current_state['instruction'] = msg.data
    
    def pose_callback(self, msg):
        self.get_logger().info(f'Received pose: {msg.data}')
        self.current_state['current_pose'] = msg.data

    def observation_callback(self, msg):
        self.get_logger().info(f'Received observation: {msg.data}')
        self.current_state['current_observation'] = msg.data

    def run_agent(self):
        if not self.current_state['instruction']:
            self.get_logger().debug('No instruction available; skipping agent tick.')
            return

        try:
            message = self.agent.run_agent(self.current_state)

            for _ in range(self.max_tool_iterations):
                tool_calls = getattr(message, 'tool_calls', None) or []
                if not tool_calls:
                    content = getattr(message, 'content', '') or ''
                    if content:
                        self.get_logger().info(f'Agent response: {content}')
                    break

                for tool_call in tool_calls:
                    result = self.execute_tool_call(tool_call)
                    self.agent.messages.append({
                        'role': 'tool',
                        'tool_call_id': tool_call.id,
                        'content': json.dumps(result),
                    })
                    record = {
                        'tool': tool_call.function.name,
                        'args': self._tool_arguments(tool_call),
                        'result': result,
                    }
                    self.current_state['history'].append(record)
                    self.log_history_to_disk(record)

                message = self.agent.client.get_response(self.agent.messages)
                self.agent.messages.append(message)
        except Exception as exc:
            self.get_logger().error(f'Agent loop failed: {exc}')

    def log_history_to_disk(self, record):
        try:
            with open('vlm_history.jsonl', 'a') as f:
                f.write(json.dumps(record) + '\n')
        except Exception as e:
            self.get_logger().error(f'Failed to log history to disk: {e}')

    def execute_tool_call(self, tool_call):
        tool_name = tool_call.function.name
        args = self._tool_arguments(tool_call)

        if tool_name == 'observe':
            return {'observation': self.current_state['current_observation']}

        if not self.action_client.wait_for_service(timeout_sec=0.5):
            raise RuntimeError('Action service /actions is not available')

        request = Tool.Request()
        request.tool_name = tool_name
        request.args_json = json.dumps(args)

        future = self.action_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            raise TimeoutError(f'Action service timed out for {tool_name}')

        response = future.result()
        if not response.success:
            raise RuntimeError(response.error or f'Action {tool_name} failed')

        return json.loads(response.result_json) if response.result_json else {}

    def _tool_arguments(self, tool_call):
        arguments = tool_call.function.arguments or {}
        if isinstance(arguments, str):
            return json.loads(arguments) if arguments else {}
        return arguments


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
