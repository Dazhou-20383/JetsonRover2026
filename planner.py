from client import OllamaClient
from prompts import agent_prompt, build_current_state_context
from tools import tools

client = OllamaClient()

current_state = build_current_state_context()

messages = [
    {"role": "system", "content": agent_prompt},
    {"role": "user", "content": current_state},
    ]

completion = client.chat.completions.create(
    model="batiai/gemma4-e2b:q4",
    messages=messages,
    tools=tools,
    tool_choice="auto",
    temperature=0.1,
)

print(completion.choices[0].message.content)