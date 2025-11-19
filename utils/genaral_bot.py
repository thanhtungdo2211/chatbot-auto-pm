import sys
from pathlib import Path

# Lấy thư mục gốc của project (ASSIGMENT_TASK)
FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]  # đi lên 1 cấp từ utils → ASSIGMENT_TASK
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from llm.llm_client import LLMClient
from prompt.utils.prompt_genaral_bot import GENERAL_BOT_PROMPT
class GenaralBot:
    def __init__(self):
        self.llm = LLMClient()
    def gen_response(self, selected_history, query):
        prompt = GENERAL_BOT_PROMPT.format(selected_history = selected_history or "No previous conversation.", query = query)
        return self.llm.generate_response(prompt)