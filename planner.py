from client import OllamaClient
from prompts import agent_prompt, build_current_state_context

client = OllamaClient()

current_state = build_current_state_context()

messages = [
    {"role": "system", "content": agent_prompt},
    {"role": "user", "content": current_state},
    ]

completion = client.chat.completions.create(
    model="Qwen/Qwen3.5-0.8B",
    messages=messages,
)

print(completion.choices[0].message.content)