from client import OllamaClient
from prompts import agent_prompt, build_current_state_context
from tools import tools

client = OllamaClient()

current_state = build_current_state_context()

messages = [
    {"role": "system", "content": agent_prompt},
    {"role": "user", "content": current_state},
    ]

response = client.get_response(messages)

print(response)

# place holder agent class for parsing the response and executing the tool calls
class VLMAgent:
    def __init__(self, client, tools):
        self.history = []

    def decide_action(self, current_state):
        messages = [
            {"role": "system", "content": agent_prompt},
            {"role": "user", "content": build_current_state_context(current_state)},
        ]

        action = self.client.get_action(messages)

        return action