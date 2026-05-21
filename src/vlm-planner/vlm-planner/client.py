from openai import OpenAI


class OllamaClient:
    def __init__(self,
                 model="batiai/gemma4-e2b:q4",
                 tools=None,
                 max_tokens=1024,
                 temperature=1.0, 
                 thinking=False,
                 **kwargs):
        
        self.tools = tools or []
        
        self.client = OpenAI(base_url="http://localhost:11434/v1", api_key="not-needed", )

    def response(self, messages):
        response = self.client.chat.completions.create(
            model="batiai/gemma4-e2b:q4",
            messages=messages,
        )