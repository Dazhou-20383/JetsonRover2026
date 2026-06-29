import base64
import re
import cv2
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from openai import OpenAI
from .prompts import agent_prompt

class OllamaClient:
    def __init__(self,
                 model="qwen3.5:2b",
                 tool_executor=None,
                 tools=None,
                 max_tokens=1024, 
                 think=False,
                 server_ip="localhost",
                 **kwargs):
        
        self.tools = tools or []
        self.model = model
        self.max_tokens = max_tokens
        self.think = think
        
        self.bridge = CvBridge()
        self.client = OpenAI(base_url=f"http://{server_ip}:11434/v1", api_key="not-needed")

    def get_response(self, state):
        img = state['current_observation']
        base64_image = self.ros2_image_to_base64(img)
        img_url = f"data:image/jpeg;base64,{base64_image}"

        state_context = self.build_current_state_context(state)

        messages = [
            {"role": "system", "content": agent_prompt},
            *state['history'],
            {"role": "user", "content": [
                {"type": "text", "text": state_context},
                {"type": "image_url", "image_url": {"url": img_url}},
                ]
            }
        ]

        state['history'].append(
            {"role": "user", "content": [
                {"type": "text", "text": state_context}
            ]
            }
        )
        print(*state['history'])
        output = self.send_request(messages)

        return output

    def send_request(self, messages):
        normalized_messages = [
            message.model_dump(exclude_none=True) if hasattr(message, 'model_dump') else message
            for message in messages
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=normalized_messages,
            tools=self.tools,
            tool_choice="auto",
            temperature=0.05,
            max_tokens=self.max_tokens,
            reasoning_effort="none",
            extra_body={"keep_alive": -1}
        )

        return response
    
    def point_image(self, image: str, description: str) -> tuple[int, int]:
        """Point to a location in an image based on a text description.

        Args: 
            image (str): base64 encoded JPEG image string.
            description (str): text description of the point to locate in the image.
            
        Returns:
            (x, y) pixel coordinates of the described point, or (0, 0) if no point matches the description
        """

        if not image:
            print("No image provided to point_image, returning (0, 0)")
            return (0, 0)

        image_url = f"data:image/jpeg;base64,{image}"

        prompt = (
            "Give the bounding box of"
            f"{description}\n"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            temperature=0.1,
            max_tokens=300,
            reasoning_effort="none",
            extra_body={"keep_alive": -1}
        )

        content = response.choices[0].message.content

        bounding_box = content.get("bounding_box", None)
        # bounding box format: [x_{min}, y_{min}, x_{max}, y_{max}]

        if not bounding_box:
            print("No coordinates found in model response, returning (0, 0)")
            print("Model response content was: '", content, "'")
            return (0, 0)

        x = (bounding_box[0] + bounding_box[2]) / 2
        y = (bounding_box[1] + bounding_box[3]) / 2

        return x, y
    
    def build_current_state_context(self, state):
        # This function should build the current state context string based on the input data.
        # For demonstration purposes, we will return a placeholder string.
        return """Instruction: {instruction}
            Current Pose: {current_pose}
            Current Waypoint: {current_waypoint}""".format(**state)

    def ros2_image_to_base64(self, ros_image: Image) -> str:
        """Converts a ROS2 Image message to a Base64 encoded string."""
        # 2. Convert ROS2 Image to OpenCV Image (BGR format)
        cv_img = self.bridge.imgmsg_to_cv2(ros_image, desired_encoding='bgr8')
        
        # 3. Compress the OpenCV image into a JPEG buffer
        # Change '.jpg' to '.png' if you need lossless compression
        success, encoded_image = cv2.imencode('.jpg', cv_img)
        if not success:
            raise ValueError("Failed to compress OpenCV image to JPEG format")
            
        # 4. Convert the buffer to bytes and then to a Base64 string
        byte_data = encoded_image.tobytes()
        base64_string = base64.b64encode(byte_data).decode('utf-8')
        
        return base64_string
