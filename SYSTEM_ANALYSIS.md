# Phân tích chi tiết hệ thống Chatbot Auto PM (tiếng Việt)

## 1. Kiến trúc & thành phần
- **Framework**: FastAPI. Điểm vào `infrastructure/api/main.py`.
- **Layers (Clean-ish)**:
  - Infrastructure: API models, deps, Redis memory, Plane client, LLM providers.
  - Application: ChatService (điều phối), QAService, ProjectManagementService, AssignmentService, ReportSessionManager, WorkReportExtractor.
  - Domain: Models, prompts, tools interfaces, memory interface.
- **LLM**: `general_bot` + router (intent classifier). Prompt templates trong `domain/prompts/templates.py`.
- **Persistence**:
  - Redis: lưu lịch sử hội thoại (10 tin), wrapper MemoryWrapper giới hạn lịch sử khi lấy.
  - In-memory dict: `active_sessions` (luồng project/assignment/update), `ReportSessionManager.sessions` (luồng báo cáo) — không chia sẻ giữa process.
- **Tích hợp Plane**: `plane_client/plane_api_client.py` (projects/issues/members CRUD). Dùng API key, workspace slug từ env.

## 2. API chính
- `POST /chat`:
  - Input: `user_id`, `role` (manager|staff), `query`, `mode_report`, `file_content`, `long_memory`.
  - Output: `response`, `mode_report`, `success`, `error`.
- `POST /reports/extract`: trích xuất báo cáo text→JSON (LLM).
- `POST /memory/clear`: xóa lịch sử hội thoại theo user_id.

## 3. Luồng Chat theo vai trò
### 3.1 Staff
- Không dùng router khi `mode_report=false` → chỉ QA trên task của chính user (filter assignee).
- `mode_report=true`:
  - ReportSessionManager quản lý state: `mode_report`, `report_text`, `infor_report`, `status`.
  - Nhận diện câu báo cáo; dùng LLM để rewrite/bổ sung `report_text`.
  - “kết thúc báo cáo” → đẩy `report_text` vào description các task assignee=user_id (best-effort) → `mode_report=false`.
  - Có thể hỏi tóm tắt báo cáo.
  - Câu không liên quan project/task/report: QA fallback general bot (nếu QA rỗng) vẫn giữ mode_report.

### 3.2 Manager
- `mode_report=false`: logic cũ với router:
  - Intent: create/update project, assignment, QA, other_topics, update_plane_information.
  - Active session: create_new_project / update_existing_information / assignment; quản lý hủy/confirm.
- `mode_report=true`:
  - Ưu tiên xử lý report/review qua ReportSessionManager.
  - Nhận diện câu đánh giá/báo cáo, rewrite với LLM, lưu `report_text`.
  - “kết thúc báo cáo” → push vào Plane, `mode_report=false`.
  - Cho phép hỏi tóm tắt báo cáo.
  - Giữ nguyên các active session khác (không phá luồng create/update/assignment đang chạy).

## 4. ReportSessionManager (file `application/report_session.py`)
- State per user: `mode_report`, `infor_report`, `report_text`, `status`, `role`.
- Nhận diện: report statement, review statement (manager), finish, info request.
- Khi mode_report bật: seed query đầu tiên vào `report_text`.
- LLM rewrite: dùng `general_bot.generate_response` với prompt cập nhật báo cáo; fallback append nếu lỗi.
- Push Plane: append `report_text` vào description các issue có `assignee=str(user_id)`; best-effort, trả thông báo.

## 5. QAService (file `application/qa_service/qa_service.py`)
- Hybrid RAG: dense (OpenAI embeddings) + sparse TF-IDF; rerank; type boost (issue>project>member).
- GraphStructuredRetriever: tổ chức theo project→issues→members, format context.
- `assignee_filter`: truyền vào `list_issues` để lọc (dùng cho staff).
- Prompt `PROMPT_QA_RAG` sinh câu trả lời dựa trên context.

## 6. ProjectManagementService
- Tạo project từ file (LLM extractor), xác nhận, tạo tasks.
- Update/create/delete project/task; add/remove member; confirm trước khi thực thi.
- Heuristic mapping field thân thiện → Plane fields.

## 7. AssignmentService
- (Chưa chi tiết lại trong thay đổi) dùng LLM để phân công; quản lý session assignment tương tự.

## 8. Memory
- RedisMemory: lưu tối đa 10 tin/ user, key `chat_history:{user_id}`.
- MemoryWrapper: `get_history(limit)` để lấy gần nhất; `clear_history`.
- select_relevant_history đã bỏ (không LLM chọn lọc).

## 9. Điểm rủi ro / hạn chế
- Mapping assignee: hiện dùng `assignee=str(user_id)`; nếu ID Plane ≠ user_id → QA lọc và push báo cáo có thể không đúng người. Cần ánh xạ user→Plane member ID/email.
- State in-memory: `active_sessions`, `report_manager.sessions` không chia sẻ giữa process/instance; restart/scale out sẽ mất state.
- Push report: append description, có thể trùng lặp nếu push nhiều lần; chưa định dạng HTML.
- Heuristic nhận diện báo cáo/review: dựa từ khóa, có thể false positive/negative.
- History limit 5 (khi gửi LLM) và 10 (lưu) có thể thiếu ngữ cảnh dài.
- Chưa có test tự động cho report session và branch role mới.

## 10. Đề xuất cải tiến
- Thêm mapping user→Plane assignee id/email; hoặc cho phép truyền assignee trong header.
- Lưu state session/report vào Redis/DB để chịu được scale/restart.
- Thêm flag/idempotency khi push report để tránh duplicate append; hoặc lưu block có marker.
- Nâng nhận diện báo cáo/review bằng classifier/LLM router riêng (schema JSON).
- Mở rộng history khi cần cho report rewrite; hoặc lưu report_text ngoài memory chat.
- Bổ sung test tự động: unit ReportSessionManager, integration ChatService với fake QA/Plane.
- Cho phép chọn format push (Markdown/HTML) và project/issue target rõ ràng.

## 11. Hướng dẫn test thủ công (rút gọn)
- Staff:
  - mode_report=false: hỏi task của mình → thấy QA trả lời; hỏi chuyện phiếm → general bot.
  - mode_report=true: gửi câu báo cáo → được ghi nhận/LLM rewrite; “tóm tắt báo cáo” → thấy nội dung; “kết thúc báo cáo” → push Plane, mode_report=false.
- Manager:
  - mode_report=false: tạo/update/assignment/QA vẫn hoạt động.
  - mode_report=true: câu đánh giá/báo cáo → ghi/LLM rewrite; “tóm tắt báo cáo”; “kết thúc báo cáo” → push Plane, không phá active_session khác.
- Plane push: kiểm tra description issues assignee=user_id đã được append report_text.

## 12. File liên quan chính
- `infrastructure/api/main.py`, `models.py`, `dependencies.py`
- `application/chat_service/chat_service.py`
- `application/report_session.py`
- `application/qa_service/qa_service.py`
- `application/project_management_service/project_management_service.py`
- `infrastructure/plane_client/plane_api_client.py`
- `infrastructure/llm_providers/*`
- `domain/prompts/templates.py`

