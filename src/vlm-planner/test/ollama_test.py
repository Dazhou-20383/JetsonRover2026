import os
import base64
import time
from vlm_planner.client import OllamaClient
from vlm_planner.tools import tools

server_ip = os.environ.get("OLLAMA_SERVER_IP", "10.42.0.221")

def test_get_response():
    client = OllamaClient(model="qwen3.5:2b", server_ip=server_ip)
    
    # Test get_response
    messages = [{"role": "user", "content": "Reply with only the word 'Hello'"}]
    response = client.get_response(messages)
    
    print("\nReal Ollama response:", response.content)

def test_point_image():
    # Initialize the actual client
    client = OllamaClient(model="qwen3.5:2b", server_ip=server_ip)
    
    # Load the dummy jpeg from example.jpeg
    image_path = os.path.join(os.path.dirname(__file__), "example.jpeg")
    with open(image_path, "rb") as image_file:
        dummy_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    # print(dummy_base64[:100] + "...")  # Print the first 100 characters of the base64 string for verification
    description = "the white swan"
    
    # Test point_image using the real model
    x, y = client.point_image(dummy_base64, description)
 
    print(f"\nReal point returned: ({x}, {y})")

def test_tool_use():
    client = OllamaClient(tools=tools, model="qwen3.5:2b", server_ip=server_ip)
    messages = [{"role": "user", "content": "Place a waypoint at (1.0, 2.0)"}]
    response = client.get_response(messages)
    print("\nReal Ollama response with tool use:", response.content)
    print("Tool calls:", getattr(response, 'tool_calls', None))



if __name__ == "__main__":
    # test_get_response()
    # test_get_response()
    # print("finish text test")
    test_point_image()
    test_point_image()
    start = time.time()
    test_point_image()
    end = time.time()
    print(f"Time taken for point_image test: {end - start:.2f} seconds")
    # test_tool_use()
    # test_tool_use()
    # print("finish tool use test")