from pydantic import BaseModel, Field
from typing import Literal
import sys
from pathlib import Path

# Lấy thư mục gốc của project (ASSIGMENT_TASK)
FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]  # đi lên 1 cấp từ utils → ASSIGMENT_TASK
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from llm.llm_client import LLMClient
from prompt.utils.prompt_router import PROMPT_ROUTER
class IntentResult(BaseModel):
        intent: Literal[
            "create_new_project",
            "update_existing_information",
            "ask_about_existing_information",
            "update_plane_information",
            "assignment",
            "other_topics",

        ] = Field(..., description="Intent classification label")
class Router:
    def __init__(self):
        self.llm = LLMClient()

    def predict(self, selected_history: str, query: str) -> str:
        # 🧠 Prompt hướng dẫn model
        prompt = PROMPT_ROUTER.format(selected_history = selected_history or "No previous conversation.", query = query)

        # 🧩 Structured output ép về schema Pydantic
        result = (
            self.llm.generate_response(prompt, IntentResult)
        )

        return result.intent
