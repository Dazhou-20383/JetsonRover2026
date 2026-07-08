import rclpy
from rclpy.qos import QoSProfile, HistoryPolicy, ReliabilityPolicy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Pose2D
from sensor_msgs.msg import Image
from custom_msgs.srv import Tool
import json
import collections
import time
import signal
import threading

from .client import OllamaClient
from .utils import Logger
from .tools import tools

class VLMNode(Node):
    def __init__(self):
        super().__init__('vlm_node')

        self.client_cb_group = ReentrantCallbackGroup()
        self.action_client = self.create_client(Tool, '/actions', callback_group=self.client_cb_group)

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
            'history': [],
        }

        self.history_logger = Logger(conv_limit=3)

        self.state_pub = self.create_publisher(String, '/agent/state', 10)
        
        self.get_logger().info('VLM Node has been started.')
        self.run_agent()

    def instruction_callback(self, msg):
        self.current_state['instruction'] = msg.data
    
    def pose_callback(self, msg):
        self.current_state['current_pose'] = msg.data

    def observation_callback(self, msg):
        self.current_state['current_observation'] = msg

    def run_agent(self):
        if self.agent_timer is not None:
            try:
                self.agent_timer.cancel()
                self.destroy_timer(self.agent_timer)
            except Exception:
                self.get_logger().debug('Timer already cancelled/destroyed')
            finally:
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

            content = getattr(message, 'content', None) or ''
            tool_calls = getattr(message, 'tool_calls', None) or []

            # Update current state history
            history = []

            state_context = self.client.build_current_state_context(self.current_state)
            history.append(
                {"role": "user", "content": [
                    {"type": "text", "text": state_context}
                ]
                }
            )

            assistant_message = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ]
            history.append(assistant_message)

            self.get_logger().info(f"Agent response: {content}")

            for tool_call in tool_calls:
                self.get_logger().info(
                    f"Agent action: {tool_call.function.name}({json.dumps(self._tool_arguments(tool_call))})"
                )
                try:
                    result = self.execute_tool_call(tool_call)
                except Exception as tool_exc:
                    self.get_logger().error(f'Tool call {tool_call.function.name} failed: {tool_exc}')
                    result = {'error': str(tool_exc)}

                self.get_logger().info(
                    f"Agent result: {tool_call.function.name} -> {json.dumps(result)}"
                )
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                })

                self.history_logger.log(history)

        except Exception as exc:
            self.get_logger().error(f'Agent loop failed: {exc}')

        self.current_state['history'] = self.history_logger.get_history()

        self.state_pub.publish(String(data=json.dumps(list(self.current_state['history']))))
        self.get_logger().info(f"Current state history: {list(self.current_state['history'])}")
        self._loop_agent()

    def log_history_to_disk(self, record):
        try:
            with open('vlm_history.jsonl', 'a') as f:
                f.write(json.dumps(record) + '\n')
        except Exception as e:
            self.get_logger().error(f'Failed to log history to disk: {e}')

    def execute_tool_call(self, tool_call, timeout=5.0):
        tool_name = tool_call.function.name
        args = self._tool_arguments(tool_call)

        if not self.action_client.wait_for_service(timeout_sec=0.5):
            raise RuntimeError('Action service /actions is not available')

        request = Tool.Request()
        request.tool_name = tool_name
        request.args_json = json.dumps(args)

        future = self.action_client.call_async(request)
        done_event = threading.Event()
        future.add_done_callback(lambda f: done_event.set())

        if not done_event.wait(timeout):
            raise TimeoutError(f'Tool call {tool_name} timed out after {timeout} seconds')

        response = future.result()

        return json.loads(response.result_json) if response.result_json else {}

    def _tool_arguments(self, tool_call):
        arguments = tool_call.function.arguments or {}
        if isinstance(arguments, str):
            return json.loads(arguments) if arguments else {}
        return arguments
    
    def _loop_agent(self):
        self.agent_timer = self.create_timer(0.2, self.run_agent)


def _install_shutdown_handlers(node):
    def _handle_shutdown(signum, frame):
        if rclpy.ok():
            node.get_logger().info(f'Received signal {signum}, shutting down.')
            rclpy.try_shutdown()

    signal.signal(signal.SIGINT, _handle_shutdown)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _handle_shutdown)


def main(args=None):
    rclpy.init(args=args)
    node = VLMNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    _install_shutdown_handlers(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

if __name__ == '__main__':
    main()
