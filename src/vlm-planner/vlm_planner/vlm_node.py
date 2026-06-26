import rclpy
from rclpy.qos import QoSProfile, HistoryPolicy, ReliabilityPolicy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Pose2D
from sensor_msgs.msg import Image
from action_msgs.srv import Tool
import json
import collections
import time

from .client import OllamaClient

from .tools import tools

class VLMNode(Node):
    def __init__(self):
        super().__init__('vlm_node')

        self.action_client = self.create_client(Tool, '/actions')

        qos_profile = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT
        )

        self.instruction_sub = self.create_subscription(String, '/robot/directions', self.instruction_callback, 2)
        self.pose_sub = self.create_subscription(Pose2D, '/robot/pose', self.pose_callback, 2)
        self.observation_sub = self.create_subscription(Image, '/camera/image_raw', self.observation_callback, qos_profile)

        self.client = OllamaClient(tools=tools, max_tokens=512)

        self.agent_timer = None
        self.current_state = {
            'instruction': '',
            'current_pose': '',
            'current_waypoint': '',
            'current_observation': None,
            'history': collections.deque(maxlen=6),
        }
        
        self.get_logger().info('VLM Node has been started.')
        self.run_agent()

    def instruction_callback(self, msg):
        # TODO: split instruction into distance, direction, and landmark
        self.get_logger().info(f'Received instruction: {msg.data}')
        self.current_state['instruction'] = msg.data
    
    def pose_callback(self, msg):
        self.get_logger().info(f'Received pose: {msg.data}')
        self.current_state['current_pose'] = msg.data

    def observation_callback(self, msg):
        self.get_logger().info(f'Received observation')
        self.current_state['current_observation'] = msg

    def run_agent(self):
        if self.agent_timer is not None:
            self.agent_timer.cancel()
            self.destroy_timer(self.agent_timer) # Clean up memory
            self.agent_timer = None
    
        self.get_logger().info('Running agent decision loop...')
        try:
            if not self.current_state['instruction'] or self.current_state['current_observation'] is None:
                self.get_logger().debug('No instruction available; skipping agent tick.')
                time.sleep(1)
                self._loop_agent()
                return
            
            response = self.client.get_response(self.current_state)
            message = response.choices[0].message

            content = getattr(message, 'content', '') or ''
            if content:
                self.current_state['history'].append({"role": "assistant", "content": content})
            self.get_logger().info(f"Agent response: {content}")

            tool_calls = getattr(message, 'tool_calls', None) or []

            for tool_call in tool_calls:
                self.get_logger().info(
                    f"Agent action: {tool_call.function.name}({json.dumps(self._tool_arguments(tool_call))})"
                )
                result = self.execute_tool_call(tool_call)

                self.get_logger().info(
                    f"Agent result: {tool_call.function.name} -> {json.dumps(result)}"
                )

                self.current_state['history'].append({
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": result,
                })

                tool_record = {
                    'tool': tool_call.function.name,
                    'args': self._tool_arguments(tool_call),
                    'result': result,
                }
                print(f"Tool call record: {json.dumps(tool_record)}")

            self.get_logger().debug(f"Current state history: {json.dumps(list(self.current_state['history']))}")


        except Exception as exc:
            self.get_logger().error(f'Agent loop failed: {exc}')

        self._loop_agent()

    def log_history_to_disk(self, record):
        try:
            with open('vlm_history.jsonl', 'a') as f:
                f.write(json.dumps(record) + '\n')
        except Exception as e:
            self.get_logger().error(f'Failed to log history to disk: {e}')

    def execute_tool_call(self, tool_call):
        tool_name = tool_call.function.name
        args = self._tool_arguments(tool_call)

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
    
    def _loop_agent(self):
        self.agent_timer = self.create_timer(0.2, self.run_agent)


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
