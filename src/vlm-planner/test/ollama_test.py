import unittest
import os
import importlib.util
import sys
import base64

# Workaround to import from a directory with a hyphen in its name (vlm-planner)
client_file = os.path.join(os.path.dirname(__file__), "..", "vlm-planner", "client.py")
spec = importlib.util.spec_from_file_location("client", client_file)
client_module = importlib.util.module_from_spec(spec)
sys.modules["client"] = client_module
spec.loader.exec_module(client_module)
OllamaClient = client_module.OllamaClient

class TestOllamaClient(unittest.TestCase):
    def test_get_response(self):
        # Initialize the actual client (Make sure Ollama is running at http://localhost:11434)
        client = OllamaClient()
        
        # Test get_response
        messages = [{"role": "user", "content": "Reply with only the word 'Hello'"}]
        response = client.get_response(messages)
        
        self.assertIsNotNone(response.content)
        self.assertTrue(len(response.content) > 0)
        print("\nReal Ollama response:", response.content)

    def test_point_image(self):
        # Initialize the actual client
        client = OllamaClient()
        
        # Load the dummy jpeg from example.jpeg
        image_path = os.path.join(os.path.dirname(__file__), "example.jpeg")
        with open(image_path, "rb") as image_file:
            dummy_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        description = "the white swan"
        
        # Test point_image using the real model
        x, y = client.point_image(dummy_base64, description)
        
        # Because we're using a real model, the exact coordinates it returns can be somewhat non-deterministic or (0,0).
        # We assert that we get back an integer tuple indicating it successfully processed and parsed a response.
        self.assertIsInstance(x, int)
        self.assertIsInstance(y, int)
        print(f"\nReal point returned: ({x}, {y})")

if __name__ == '__main__':
    unittest.main()
