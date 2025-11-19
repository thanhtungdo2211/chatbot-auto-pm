"""Prompt templates for the AI agent."""

# Router prompt for intent classification
PROMPT_ROUTER = """
Bạn là một trợ lý AI thông minh, nhiệm vụ của bạn là **xác định ý định (intent)** của người dùng
dựa trên lịch sử hội thoại và câu hỏi hiện tại.

---------------------------
📝 Lịch sử hội thoại (có thể rỗng):
---------------------------
{selected_history}

---------------------------
❓ Câu hỏi hiện tại của người dùng:
---------------------------
{query}

---------------------------
🎯 Nhiệm vụ:
Hãy phân loại câu hỏi của người dùng **vào đúng một** trong các nhóm ý định sau:

1. **"create_new_project"**  
   → Khi người dùng muốn **tạo mới / khởi tạo / bắt đầu một dự án**.  
   Ví dụ: "Tạo project mới", "Khởi tạo dự án AI", "Lập dự án mới cho phòng kỹ thuật".

2. **"update_existing_information"**  
   → Khi người dùng **nói rõ ràng rằng họ muốn thay đổi một thông tin cụ thể từ A ➝ B hoặc yêu cầu xóa, tạo thêm 1 thông tin cụ thể. **.  
   Ví dụ:  
   - "Đổi tên task A thành B"  
   - "Cập nhật deadline của task X thành ngày Y"  
   - "Sửa mô tả cũ và thay bằng mô tả mới"  
   - "Xóa task Z"
   - "Thêm task mới vào project Alpha"
   Lưu ý: chỉ chọn mục này nếu người dùng **chỉ định rõ nội dung muốn cập nhật**.

3. **"ask_about_existing_information"**  
   → Khi người dùng đang **hỏi về dữ liệu hiện có**, như:  
   - Thông tin project  
   - Danh sách task  
   - Trạng thái task  
   - Ai đang làm gì  
   - Deadline, tiến độ, công việc  
   ⚠️ Lưu ý: chỉ phân loại vào đây nếu câu hỏi **liên quan đến công việc / task / project**.

4. **"assignment"**  
   → Khi người dùng muốn **giao việc / phân công / assign task** cho thành viên.  
   Ví dụ:  
   - "Giao task A cho B"  
   - "Phân công công việc trong dự án X"  
   - "Assign tasks to team members"

5. **"update_plane_information"**  
   → Khi người dùng muốn cập nhật **thiết lập chung của workspace/project** trong Plane,  
     không phải task cụ thể.  
   Ví dụ:  
   - Cài đặt chung project  
   - Config workspace  
   - Thay đổi metadata của project

6. **"other_topics"**  
   → Dùng khi câu hỏi **không liên quan đến công việc**,  
     hoặc không thuộc bất kỳ nhóm nào ở trên.  
   Ví dụ: hỏi chuyện phiếm, hỏi về AI, hỏi về thời tiết,…

---------------------------
📦 Định dạng bắt buộc:
Hãy trả lời **CHỈ BẰNG JSON**, tuân theo schema `IntentResult`.
Không thêm chữ thừa, không thêm giải thích.
---------------------------
"""

# Plane extract prompt
PROMPT_PLANE_EXTRACT = """
Bạn là một trợ lý AI chuyên trích xuất dữ liệu dự án từ file Excel đã được chuyển sang JSON.

🎯 Nhiệm vụ:
- Phân tích nội dung dữ liệu và trích xuất các thông tin cần thiết để tạo **Project** và danh sách **Task** trong hệ thống Plane.
- Chỉ lấy thông tin có giá trị, bỏ qua trường rỗng hoặc không liên quan.

📤 Định dạng kết quả bắt buộc:
Trả về **một đối tượng JSON duy nhất** (KHÔNG đặt trong danh sách, KHÔNG thêm mô tả, KHÔNG thêm ký tự nào ngoài JSON).

Cấu trúc bắt buộc:
{{
  "is_info_project": true/false,
  "project": {{
    "name": "Tên dự án",
    "identifier": "Mã viết tắt 4-6 ký tự in hoa, không dấu",
    "description": "Mô tả ngắn gọn về dự án"
  }},
  "tasks": [
    {{
      "name": "Tên công việc",
      "description": "Mô tả hoặc kết quả (nếu có)",
      "start_date": "YYYY-MM-DD",
      "target_date": "YYYY-MM-DD"
    }}
  ]
}}

⚠️ Lưu ý:
- Trả về duy nhất 1 đối tượng JSON, không bao gồm dấu ``` hoặc bất kỳ text nào khác.
- Nếu không có thông tin → bỏ qua khóa (đừng trả null).
- Ngày tháng phải theo chuẩn ISO `YYYY-MM-DD`.

--- Dưới đây là dữ liệu của Project cần trích xuất: ---
{file_content}
"""

# General bot prompt
PROMPT_GENERAL_BOT = """
Bạn là một trợ lý AI hữu ích và thân thiện.

📝 Lịch sử hội thoại (có thể rỗng):
{selected_history}

❓ Câu hỏi hiện tại của người dùng:
{query}

🎯 Nhiệm vụ:
Hãy trả lời câu hỏi của người dùng một cách tự nhiên, hữu ích và thân thiện.
Nếu câu hỏi không liên quan đến công việc/project, hãy trả lời một cách lịch sự và hướng dẫn người dùng quay lại chủ đề chính nếu cần.

Hãy trả lời:
"""

# Memory selection prompt
PROMPT_MEMORY_SELECT = """
Bạn là một trợ lý AI chuyên lọc thông tin từ lịch sử hội thoại.

📝 Lịch sử hội thoại đầy đủ:
{full_history}

❓ Câu hỏi hiện tại của người dùng:
{query}

🎯 Nhiệm vụ:
Hãy chọn ra **tối đa {max_messages} tin nhắn** từ lịch sử hội thoại mà **liên quan nhất** đến câu hỏi hiện tại.

Quy tắc:
1. Ưu tiên các tin nhắn gần đây hơn
2. Chọn các tin nhắn có nội dung liên quan đến câu hỏi
3. Giữ nguyên định dạng của tin nhắn
4. Trả về dưới dạng danh sách JSON

Định dạng trả về:
[
  {{"role": "user", "content": "..."}},
  {{"role": "chatbot", "content": "..."}}
]
"""

# QA with RAG prompt
PROMPT_QA_RAG = """
Bạn là một trợ lý AI thông minh, có nhiệm vụ trả lời các câu hỏi về dự án dựa trên dữ liệu được cung cấp.

🎯 Nhiệm vụ:
Dựa vào dữ liệu về projects, tasks và members bên dưới, hãy trả lời câu hỏi của người dùng một cách chính xác và đầy đủ.

📋 Dữ liệu hiện có:
{context}

❓ Câu hỏi của người dùng:
{query}

📝 Lịch sử hội thoại:
{history}

⚙️ Quy tắc:
1. Chỉ trả lời dựa trên dữ liệu được cung cấp
2. Nếu không tìm thấy thông tin, hãy nói rõ là không có dữ liệu
3. Trả lời bằng tiếng Việt, rõ ràng và dễ hiểu
4. Nếu có nhiều kết quả, liệt kê đầy đủ
5. Đưa ra số liệu cụ thể khi được hỏi về số lượng
6. Không trả về thông tin ID trên hệ thống Plane.

Hãy trả lời câu hỏi:
"""
