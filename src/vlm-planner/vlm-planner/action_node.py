import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32, Bool
from geometry_msgs.msg import Point
from action_msgs.srv import Tool

import json
from client import OllamaClient


class ActionServer(Node):
    def __init__(self):
        super().__init__('action_node')
        self.action_srv = self.create_service(Tool, '/actions', self.action_callback)
        
        # Route to mbra
        self.mbra_pub = self.create_publisher(Point, '/mbra/waypoints', 10)
        # TODO: get image for self.vlm.point_image()
        
        # client to rover controller
        self.stop_client = self.create_client(String, '/actions/stop')
        self.turn_client = self.create_client(Float32, '/actions/turn')
        self.mbra_client = self.create_client(Bool, '/actions/enable_mbra')

        self.vlm = OllamaClient()

        self.get_logger().info('Action Node has been started.')

        self.tools = {
            'observe': self.observe,
            'stop': self.stop,
            'turn_right': self.turn_right,
            'turn_left': self.turn_left,
            'turn_towards': self.turn_towards,
            'place_waypoint': self.place_waypoint,
            'place_waypoint_precise': self.place_waypoint_precise
        }


    def action_handler(self, request, response):
        self.get_logger().info(f'Received action: {request.tool_name} with payload: {request.args_json}')

        try: 
            tool_name = request.tool_name
            payload = json.loads(request.args_json)
                

            self.get_logger().warn(f'Unknown action: {request.tool_name}')

            function = self.commands[tool_name]

            # execute function with kwargs
            result = function(**payload)

            response.success = True
            response.result_json = json.dumps(result)
            response.error = ''

        except Exception as e:
            response.success = False
            response.result_json = ''
            response.error = str(e)
        
        return response
    
    def stop(self, **kwargs):
        future = self.stop_client.call(String(data='stop'))
        
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def turn_right(self, **kwargs):
        future = self.turn_client.call(Float32(data=-60))

        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def turn_left(self, **kwargs):
        future = self.turn_client.call_async(String(data=60))

        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def turn_towards(self, direction, **kwargs):
        self.current_direction = direction
        angle = self.current_direction - direction
        future = self.turn_client.call_async(Float32(data=angle))

        rclpy.spin_until_future_complete(self, future)
        return future.result()
    
    def place_waypoint(self, x, y, **kwargs):
        point = Point(x=x, y=y, z=0.0)
        self.mbra_pub.publish(point)
        future = self.mbra_client.call_async(Bool(data=True))

        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def place_waypoint_precise(self, loc_description, **kwargs):
        # TODO: get image for self.vlm.point_image()
        x, y = self.vlm.point_image(None, loc_description)
        point = Point(x=x, y=y, z=0.0)
        self.mbra_pub.publish(point)
        future = self.mbra_client.call_async(Bool(data=True))

        rclpy.spin_until_future_complete(self, future)
        return future.result()

    
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