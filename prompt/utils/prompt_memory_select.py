# prompt.py

EXTRACT_RELEVANT_HISTORY_PROMPT = """
Bạn là một trợ lý AI thông minh có nhiệm vụ hỗ trợ chatbot hiểu rõ ngữ cảnh.

Dưới đây là lịch sử hội thoại giữa người dùng và chatbot (nhiều lượt):
===
{history}
===

Và đây là câu hỏi tiếp theo của người dùng:
===
{question}
===

👉 Hãy **trích xuất các đoạn hội thoại trước có liên quan đến yêu cầu của người dùng hiện tại**.

Chỉ trả về những lượt hội thoại liên quan (dưới dạng danh sách), không cần giải thích thêm.
"""
