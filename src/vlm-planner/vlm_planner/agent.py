from prompts import agent_prompt, build_current_state_context

# place holder agent class for parsing the response and executing the tool calls
class VLMAgent:
    def __init__(self, client):
        self.history = []
        self.client = client
        self.messages = []

    def run_agent(self, current_state):
        self.messages = [
            {"role": "system", "content": agent_prompt},
            {"role": "user", "content": build_current_state_context(current_state)},
        ]

        output = self.client.get_response(self.messages)

        self.messages.append(output)

        return output
