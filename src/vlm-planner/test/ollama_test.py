import os
import base64
from vlm_planner.client import OllamaClient
from vlm_planner.tools import tools

def test_get_response():
    # Initialize the actual client (Make sure Ollama is running at http://localhost:11434)
    client = OllamaClient(model="qwen3.5:0.8b")
    
    # Test get_response
    messages = [{"role": "user", "content": "Reply with only the word 'Hello'"}]
    response = client.get_response(messages)
    
    print("\nReal Ollama response:", response.content)

def test_point_image():
    # Initialize the actual client
    client = OllamaClient(model="qwen3.5:0.8b")
    
    # Load the dummy jpeg from example.jpeg
    image_path = os.path.join(os.path.dirname(__file__), "example.jpeg")
    with open(image_path, "rb") as image_file:
        dummy_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    print(dummy_base64[:100] + "...")  # Print the first 100 characters of the base64 string for verification
    description = "the white swan"
    
    # Test point_image using the real model
    x, y = client.point_image(dummy_base64, description)
 
    print(f"\nReal point returned: ({x}, {y})")

def test_tool_use():
    client = OllamaClient(tools=tools, model="qwen3.5:0.8b")
    messages = [{"role": "user", "content": "Place a waypoint at (1.0, 2.0)"}]
    response = client.get_response(messages)
    print("\nReal Ollama response with tool use:", response.content)



if __name__ == "__main__":
    test_get_response()
    test_get_response()
    print("finish text test")
    test_point_image()
    test_point_image()
    print("finish point image test")
    test_tool_use()
    test_tool_use()
    print("finish tool use test")