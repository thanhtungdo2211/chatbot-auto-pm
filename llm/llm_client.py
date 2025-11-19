from pydantic import BaseModel
from langchain.chat_models import init_chat_model
import os
from dotenv import load_dotenv

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("API_KEY")

class LLMClient:
    def __init__(self):
        self.model_name = os.getenv("MODEL_NAME")
        self.base_url = os.getenv("BASE_URL")
        self.model_name = os.getenv("MODEL_NAME")
        self.llm = init_chat_model(model = self.model_name, model_provider="openai", base_url =self.base_url)
        self.llm_structured = None
    def generate_response(self, prompt, output_format = None):
        if output_format is not None:
            self.llm_structured = self.llm.with_structured_output(output_format)
            return self.llm_structured.invoke(prompt)
        else:
            return self.llm.invoke(prompt).content
    
# if __name__ == "__main__":
#     llm_client = LLMClient()
#     response = llm_client.generate_response("What is the capital of France?")
#     print(response)

