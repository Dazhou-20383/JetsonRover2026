from openai import OpenAI

class OllamaClient:
    def __init__(self,
                 model="batiai/gemma4-e2b:q4",
                 tool_executor=None,
                 tools=None,
                 max_tokens=1024,
                 temperature=0.1, 
                 thinking=False,
                 **kwargs):
        
        self.tools = tools or []

        self.tool_executor = tool_executor
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        self.client = OpenAI(base_url="http://localhost:11434/v1", api_key="not-needed", )

    def get_response(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
            tool_choice="auto",
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return response.choices[0].message.content
    
    def point_image(self, image, description):
        raise NotImplementedError("point_image is not implemented yet. This function should take an image and a description of a point of interest, and return the coordinates of that point in the image.")