import sys
from pathlib import Path

# Lấy thư mục gốc của project (ASSIGMENT_TASK)
FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]  # đi lên 1 cấp từ utils → ASSIGMENT_TASK
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from llm.llm_client import LLMClient
from prompt.utils.prompt_memory_select import EXTRACT_RELEVANT_HISTORY_PROMPT
class MemorySelectBot:
    def __init__(self):
        self.llm = LLMClient()
    def get_memory_select(self, history, query):
        prompt = EXTRACT_RELEVANT_HISTORY_PROMPT.format(history=history, question=query)
        return self.llm.generate_response(prompt)