import base64
import re
import cv2
from openai import OpenAI

class OllamaClient:
    def __init__(self,
                 model="qwen3.5:2b",
                 tool_executor=None,
                 tools=None,
                 max_tokens=1024,
                 temperature=0.1, 
                 think=False,
                 server_ip="localhost",
                 **kwargs):
        
        self.tools = tools or []
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.think = think
        
        self.client = OpenAI(base_url=f"http://{server_ip}:11434/v1", api_key="not-needed")

    def get_response(self, messages):
        normalized_messages = [
            message.model_dump(exclude_none=True) if hasattr(message, 'model_dump') else message
            for message in messages
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=normalized_messages,
            tools=self.tools,
            tool_choice="auto",
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_body={"keep_alive": -1}
        )

        return response.choices[0].message
    
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
        match = re.search(r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)", content)
        print(f"Model response content: '{content}'")
        if not match:
            print("No coordinates found in model response, returning (0, 0)")
            print("Model response content was: '", content, "'")
            return (0, 0)

        return (int(round(float(match.group(1)))), int(round(float(match.group(2)))))