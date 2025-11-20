from pydantic import BaseModel, Field
from typing import Optional
import json

# -----------------------------
# Prompt cho LLM
# -----------------------------
PROMPT_AFFIRMATIVE_CHECK = """
Bạn là một trợ lý AI thông minh, có nhiệm vụ phân tích tin nhắn của người dùng
và xác định xem họ có đang **đồng ý / xác nhận** (affirmative) hay không.

🎯 Nhiệm vụ:
Phân tích câu đầu vào và trả về kết quả JSON theo định dạng:

{
  "is_affirmative": true hoặc false,
  "reason": "Giải thích ngắn gọn vì sao bạn cho là đồng ý hoặc không"
}

⚙️ Quy tắc:
- Các câu như: "đúng rồi", "ok", "vâng", "dạ", "chuẩn", "yes", "tôi đồng ý" → `is_affirmative = true`
- Các câu như: "không", "chưa", "sai", "no", "từ chối" → `is_affirmative = false`
- Nếu không rõ nghĩa hoặc trung lập → `is_affirmative = false`
- Trả về duy nhất 1 JSON, không có text hay ký tự thừa.

--- Dưới đây là câu của người dùng ---
"""

# -----------------------------
# Schema định nghĩa output
# -----------------------------
class AffirmativeResult(BaseModel):
    is_affirmative: bool = Field(..., description="True nếu câu mang nghĩa đồng ý / xác nhận")
    reason: Optional[str] = Field(None, description="Giải thích ngắn gọn vì sao có kết luận này")

# -----------------------------
# Lớp chính dùng LLM
# -----------------------------
class AffirmativeChecker:
    def __init__(self, llm_client):
        self.llm = llm_client

    def check(self, query: str) -> AffirmativeResult:
        """
        Gửi query người dùng tới LLM và phân tích xem có mang tính đồng ý / xác nhận không.
        """
        prompt = PROMPT_AFFIRMATIVE_CHECK + query
        result = self.llm.generate_response(prompt, AffirmativeResult)

        # Nếu kết quả là list (tùy LLM), lấy phần tử đầu tiên
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
        return result

# -----------------------------
# Ví dụ chạy thử (giả lập LLM)
# -----------------------------
if __name__ == "__main__":
    # ✅ Giả lập LLM client (bạn thay bằng OpenAI, Gemini... tuỳ hệ thống)
    class DummyLLM:
        def generate_response(self, prompt, schema):
            text = prompt.lower()
            if any(word in text for word in ["ok", "vâng", "dạ", "yes", "đồng ý", "đúng", "chuẩn"]):
                return schema(is_affirmative=True, reason="Người dùng thể hiện sự đồng ý hoặc xác nhận.")
            return schema(is_affirmative=False, reason="Không có dấu hiệu đồng ý rõ ràng.")

    llm = DummyLLM()
    checker = AffirmativeChecker(llm)

    test_queries = [
        "OK bạn nhé",
        "Đúng rồi đó",
        "Không phải",
        "Chưa đâu",
        "Tôi đồng ý",
        "Sao cũng được"
    ]

    for q in test_queries:
        res = checker.check(q)
        print(f"{q} → {res.json()}")
