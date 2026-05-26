import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32, Bool
from geometry_msgs.msg import Point, PoseStamped
from action_msgs.srv import Tool
from action_msgs.srv import Stop as StopSrv, Turn as TurnSrv, EnableMBRA as EnableMBRASrv

import json
from typing import Any, Dict, Tuple

from client import OllamaClient


class ActionServer(Node):
    def __init__(self):
        super().__init__('action_node')
        # Service to receive high level tool requests
        self.action_srv = self.create_service(Tool, '/actions', self.action_handler)

        # Route to mbra
        self.mbra_pub = self.create_publisher(Point, '/mbra/waypoints', 10)

        # Service clients for low-level rover commands. Use typed services defined in action_msgs.
        self.stop_client = self.create_client(StopSrv, '/actions/stop')
        self.turn_client = self.create_client(TurnSrv, '/actions/turn')
        self.mbra_client = self.create_client(EnableMBRASrv, '/actions/enable_mbra')

        # Pose subscription used to compute relative turns
        # Expecting a custom Pose2D message with x, y, yaw (radians)
        self.current_orientation = 0.0
        self.current_pose = {'x': 0.0, 'y': 0.0}
        self.pose_sub = self.create_subscription(PoseStamped, '/robot/pose', self._pose_callback, 10)

        # VLM client (language + vision model wrapper)
        self.vlm = OllamaClient()

        self.get_logger().info('Action Node has been started.')

        # Mapping of tool names to handler methods
        self.tools: Dict[str, Any] = {
            'stop': self.stop,
            'turn_right': self.turn_right,
            'turn_left': self.turn_left,
            'turn_towards': self.turn_towards,
            'place_waypoint': self.place_waypoint,
            'place_waypoint_precise': self.place_waypoint_precise,
        }


    def action_handler(self, request, response):
        self.get_logger().info(f'Received action: {request.tool_name} with payload: {request.args_json}')

        try:
            tool_name = request.tool_name
            payload = json.loads(request.args_json) if request.args_json else {}

            if tool_name not in self.tools:
                msg = f'Unknown action: {tool_name}'
                self.get_logger().warn(msg)
                raise ValueError(msg)

            func = self.tools[tool_name]

            # execute function with kwargs
            result = func(**payload)

            response.success = True
            response.result_json = json.dumps(result or {})
            response.error = ''

        except Exception as e:
            self.get_logger().error(f'Action handling failed: {e}')
            response.success = False
            response.result_json = ''
            response.error = str(e)

        return response

    def _pose_callback(self, msg) -> None:
        """Pose handler expecting `Pose2D` with `x`, `y`, `yaw` (radians)."""
        try:
            self.current_pose['x'] = float(msg.x)
            self.current_pose['y'] = float(msg.y)
            self.current_orientation = float(msg.yaw)
        except Exception:
            self.get_logger().debug('Received malformed Pose2D; keeping previous pose')
    
    def stop(self, **kwargs) -> Dict[str, Any]:
        """Call the typed `Stop` service on the rover controller."""
        if not self.stop_client.wait_for_service(timeout_sec=1.0):
            msg = 'Stop service not available'
            self.get_logger().error(msg)
            raise RuntimeError(msg)

        req = StopSrv.Request()
        req.command = kwargs.get('command', 'stop')

        future = self.stop_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        res = future.result()
        return {'success': bool(res.success), 'error': getattr(res, 'error', '')}

    def turn_right(self, degrees: float = 60.0, **kwargs) -> Dict[str, Any]:
        """Turn the rover to the right by `degrees` relative to current orientation using the `Turn` service."""
        target_orientation = self.current_orientation - float(degrees)
        if not self.turn_client.wait_for_service(timeout_sec=1.0):
            msg = 'Turn service not available'
            self.get_logger().error(msg)
            raise RuntimeError(msg)

        req = TurnSrv.Request()
        req.orientation = float(target_orientation)

        future = self.turn_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        res = future.result()
        return {'success': bool(res.success), 'error': getattr(res, 'error', ''), 'target_orientation': target_orientation}

    def turn_left(self, degrees: float = 60.0, **kwargs) -> Dict[str, Any]:
        """Turn the rover to the left by `degrees` relative to current orientation using the `Turn` service."""
        target_orientation = self.current_orientation + float(degrees)
        if not self.turn_client.wait_for_service(timeout_sec=1.0):
            msg = 'Turn service not available'
            self.get_logger().error(msg)
            raise RuntimeError(msg)

        req = TurnSrv.Request()
        req.orientation = float(target_orientation)

        future = self.turn_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        res = future.result()
        return {'success': bool(res.success), 'error': getattr(res, 'error', ''), 'target_orientation': target_orientation}

    def turn_towards(self, direction: float, **kwargs) -> Dict[str, Any]:
        """Turn the rover to the absolute `direction` (same units as pose subscription) via `Turn` service."""
        direction = float(direction)
        if not self.turn_client.wait_for_service(timeout_sec=1.0):
            msg = 'Turn service not available'
            self.get_logger().error(msg)
            raise RuntimeError(msg)

        req = TurnSrv.Request()
        req.orientation = direction

        future = self.turn_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        res = future.result()
        return {'success': bool(res.success), 'error': getattr(res, 'error', ''), 'target_orientation': direction}
    
    def place_waypoint(self, x: float, y: float, **kwargs) -> Dict[str, Any]:
        """Place a waypoint by publishing a Point to the MBRA topic and enabling MBRA."""
        point = Point(x=float(x), y=float(y), z=0.0)
        self.get_logger().info(f'Publishing waypoint: ({point.x}, {point.y})')
        # publish the waypoint, then call the MBRA enable service to engage it
        self.mbra_pub.publish(point)
        if not self.mbra_client.wait_for_service(timeout_sec=1.0):
            msg = 'MBRA service not available'
            self.get_logger().error(msg)
            raise RuntimeError(msg)

        req = EnableMBRASrv.Request()
        req.enable = True
        future = self.mbra_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        res = future.result()
        return {'success': bool(res.success), 'error': getattr(res, 'error', ''), 'point': {'x': point.x, 'y': point.y}}

    def place_waypoint_precise(self, loc_description: str, **kwargs) -> Dict[str, Any]:
        """Use the VLM client to localize a described point in the current camera image and place a waypoint.

        The node will attempt to obtain an image from a camera service if available. If the image
        cannot be retrieved, `self.vlm.point_image` will be called with `None` and should handle that case.
        """
        self.get_logger().info(f'Locating described point: {loc_description}')

        try:
            x, y = self.vlm.point_image(None, loc_description)
        except Exception as e:
            self.get_logger().error(f'VLM point_image failed: {e}')
            raise

        point = Point(x=float(x), y=float(y), z=0.0)
        self.get_logger().info(f'Publishing precise waypoint: ({point.x}, {point.y})')
        self.mbra_pub.publish(point)
        if not self.mbra_client.wait_for_service(timeout_sec=1.0):
            msg = 'MBRA service not available'
            self.get_logger().error(msg)
            raise RuntimeError(msg)

        req = EnableMBRASrv.Request()
        req.enable = True
        future = self.mbra_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        res = future.result()
        return {'success': bool(res.success), 'error': getattr(res, 'error', ''), 'point': {'x': point.x, 'y': point.y}}

    
def main(args=None):
    rclpy.init(args=args)
    node = ActionServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

if __name__ == '__main__':
    main()