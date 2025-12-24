# Giải Thích Chi Tiết Source Code - Chatbot Auto PM

## 📋 Tổng Quan

Đây là một hệ thống **AI-powered Project Management Chatbot** được xây dựng bằng Python/FastAPI, tích hợp với Plane.so để quản lý dự án. Hệ thống sử dụng LLM (Large Language Model) để hiểu và xử lý yêu cầu của người dùng bằng tiếng Việt.

---

## 🏗️ Kiến Trúc Tổng Quan

Hệ thống tuân theo **Clean Architecture** với 3 lớp chính:

```
┌─────────────────────────────────────────┐
│     Infrastructure Layer (API, DB)      │
│  - FastAPI endpoints                    │
│  - Redis memory storage                 │
│  - Plane API client                     │
│  - LLM providers                        │
└─────────────────────────────────────────┘
              ↕
┌─────────────────────────────────────────┐
│     Application Layer (Services)        │
│  - ChatService (orchestrator)           │
│  - ProjectManagementService             │
│  - QAService                            │
│  - AssignmentService                    │
└─────────────────────────────────────────┘
              ↕
┌─────────────────────────────────────────┐
│     Domain Layer (Business Logic)       │
│  - Intent classification                 │
│  - Memory interface                     │
│  - Domain models                        │
│  - Prompts                              │
└─────────────────────────────────────────┘
```

---

## 📁 Cấu Trúc Thư Mục

```
src/auto_pm_agent_api/
├── infrastructure/          # Lớp hạ tầng
│   ├── api/                 # FastAPI endpoints
│   │   ├── main.py          # Entry point, định nghĩa routes
│   │   ├── models.py        # Request/Response models
│   │   └── dependencies.py  # Dependency injection
│   ├── db/                  # Database layer
│   │   └── redis_memory.py  # Redis storage cho conversation history
│   ├── llm_providers/       # LLM integration
│   │   ├── llm_client.py    # Wrapper cho OpenAI API
│   │   ├── router.py        # Intent classifier
│   │   └── general_bot.py   # General conversation bot
│   └── plane_client/        # Plane.so API client
│       └── plane_api_client.py
│
├── application/             # Lớp ứng dụng (business logic)
│   ├── chat_service/        # Service chính điều phối mọi thứ
│   ├── project_management_service/  # Tạo/cập nhật projects
│   ├── qa_service/          # Q&A với RAG
│   ├── assignment_service/   # Giao việc cho members
│   └── report_service/      # Trích xuất báo cáo công việc
│
└── domain/                  # Lớp domain (business rules)
    ├── tools/               # Intent classifier interface
    ├── memory/              # Memory interface & models
    ├── models/              # Domain models (Plane, Report)
    └── prompts/             # Prompt templates cho LLM
```

---

## 🔄 Luồng Xử Lý Chính

### 1. Entry Point: `main.py`

**File:** `src/auto_pm_agent_api/infrastructure/api/main.py`

Đây là điểm vào của ứng dụng FastAPI:

```python
@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    # 1. Nhận request từ client
    # 2. Gọi ChatService.handle_query()
    # 3. Trả về response
```

**Các endpoints:**
- `POST /chat` - Endpoint chính xử lý chat
- `POST /reports/extract` - Trích xuất báo cáo công việc
- `POST /memory/clear` - Xóa lịch sử hội thoại
- `GET /health` - Health check

### 2. Dependency Injection: `dependencies.py`

**File:** `src/auto_pm_agent_api/infrastructure/api/dependencies.py`

File này khởi tạo và kết nối tất cả các components:

```python
@lru_cache()
def get_chat_service() -> ChatService:
    # 1. Khởi tạo LLM client
    # 2. Khởi tạo Redis memory
    # 3. Khởi tạo các services (Project, QA, Assignment)
    # 4. Tạo ChatService với tất cả dependencies
    return ChatService(...)
```

**Các components được khởi tạo:**
- `LLMClient` - Kết nối với OpenAI API
- `RedisMemory` - Lưu trữ conversation history
- `Router` - Phân loại intent
- `GeneralBot` - Xử lý câu hỏi chung
- `PlaneAPIFactory` - Factory tạo Plane API client
- `ProjectManagementService`, `QAService`, `AssignmentService`

### 3. Core Service: `ChatService`

**File:** `src/auto_pm_agent_api/application/chat_service/chat_service.py`

Đây là **trái tim** của hệ thống, điều phối tất cả các luồng xử lý:

#### 3.1. Phương thức chính: `handle_query()`

```python
def handle_query(self, user_id: int, query: str, file_content: str) -> str:
    # Bước 1: Xử lý file upload (nếu có)
    if file_content:
        # Lưu file content vào session
        return "Tôi đã đọc file..."
    
    # Bước 2: Lấy lịch sử hội thoại gần nhất
    selected_history = self.memory.get_history(user_id, limit=5)
    
    # Bước 3: Kiểm tra session đang active
    active_session = self.active_sessions.get(user_id)
    
    if active_session:
        # Xử lý trong session hiện tại
        return self._handle_active_session_flow(...)
    
    # Bước 4: Phân loại intent
    intent_result = self.intent_classifier.classify(history_str, query)
    intent = intent_result.intent
    
    # Bước 5: Route đến service tương ứng
    if intent == "create_new_project":
        return self.project_service.handle_create_project(...)
    elif intent == "ask_about_existing_information":
        return self.qa_service.handle_query(...)
    elif intent == "assignment":
        return self.assignment_service.handle_assignment(...)
    # ...
```

#### 3.2. Quản lý Session

Hệ thống quản lý **multi-session** để xử lý các luồng dài:

- **create_new_project**: Tạo project từ file → Trích xuất → Xác nhận → Tạo
- **update_existing_information**: Cập nhật project/task → Xác nhận → Thực thi
- **assignment**: Giao việc → Xác nhận → Assign

**Session states:**
- `None` - Không có session
- `"create_new_project"` - Đang tạo project
- `"update_existing_information"` - Đang cập nhật
- `"waiting_confirmation"` - Chờ xác nhận
- `"ready_to_create"` - Sẵn sàng tạo

#### 3.3. Xử lý Intent Conflicts

Khi user đang trong một session nhưng hỏi câu hỏi khác:

```python
def _handle_active_session_flow(...):
    # Nếu intent mới không tương thích với session hiện tại
    if not self._is_intent_compatible(session_type, new_intent):
        # Hỏi user có muốn hủy session hiện tại không
        return self._build_cancel_prompt(...)
```

---

## 🎯 Intent Classification

### Router: `router.py`

**File:** `src/auto_pm_agent_api/infrastructure/llm_providers/router.py`

Sử dụng LLM để phân loại intent của user:

```python
class Router(IntentClassifier):
    def classify(self, history: str, query: str) -> IntentResult:
        prompt = PROMPT_ROUTER.format(
            selected_history=history,
            query=query
        )
        result = self.llm.generate_response(prompt, IntentResult)
        return result
```

**Các intent được hỗ trợ:**
1. `create_new_project` - Tạo project mới
2. `update_existing_information` - Cập nhật thông tin
3. `ask_about_existing_information` - Hỏi về thông tin hiện có
4. `update_plane_information` - Cập nhật thông tin trên Plane
5. `assignment` - Giao việc
6. `other_topics` - Chủ đề khác

---

## 📦 Project Management Service

**File:** `src/auto_pm_agent_api/application/project_management_service/project_management_service.py`

### 1. Tạo Project (`handle_create_project`)

**Luồng xử lý:**

```
User upload file
    ↓
Extract project data (LLM)
    ↓
Validate data
    ↓
Store in session
    ↓
Ask for confirmation
    ↓
User confirms
    ↓
Create project on Plane
    ↓
Create tasks
    ↓
Return success message
```

**Chi tiết:**

1. **Trích xuất dữ liệu:**
   ```python
   extracted_data = self.plane_extractor.extract(file_content)
   # Trả về: project name, description, tasks, etc.
   ```

2. **Lưu vào session:**
   ```python
   session["status"] = "ready_to_create"
   session["extracted_data"] = extracted_data
   ```

3. **Xác nhận:**
   ```python
   if self._is_affirmative(query):  # "có", "yes", "ok"
       # Tạo project trên Plane
       project = plane_api.create_project(...)
       # Tạo tasks
       for task in extracted_data.tasks:
           plane_api.create_issue(...)
   ```

### 2. Cập nhật Project/Task (`handle_update_info`)

**Hỗ trợ các hành động:**
- `create_project` - Tạo project
- `update_project` - Cập nhật project (name, description, identifier)
- `delete_project` - Xóa project
- `create_task` - Tạo task
- `update_task` - Cập nhật task (name, description, priority, dates, assignees)
- `delete_task` - Xóa task
- `add_member` - Thêm member vào project
- `remove_member` - Xóa member khỏi workspace/project

**Luồng xử lý:**

```
User: "Cập nhật deadline task X thành ngày Y"
    ↓
LLM extract: action_type="update_task", field="target_date", value="Y"
    ↓
Resolve project & task
    ↓
Prepare update info
    ↓
Ask for confirmation
    ↓
User confirms
    ↓
Execute update on Plane
    ↓
Return success
```

**Trích xuất thông tin bằng LLM:**

```python
def _extract_update_request(self, query, history):
    prompt = PROMPT_EXTRACT_UPDATE.format(
        history=history,
        query=query,
        ...
    )
    result = self.llm.generate_response(prompt, UpdateExtractResult)
    # Trả về structured data: action_type, project, task, field, value, etc.
```

---

## 🔍 QA Service với RAG

**File:** `src/auto_pm_agent_api/application/qa_service/qa_service.py`

Service này sử dụng **RAG (Retrieval-Augmented Generation)** để trả lời câu hỏi về projects/tasks.

### 1. Hybrid RAG Retriever

**Kết hợp 2 phương pháp:**
- **Dense embeddings** (OpenAI) - Hiểu ngữ nghĩa
- **Sparse TF-IDF** - Tìm từ khóa chính xác

```python
class HybridRAGRetriever:
    def search(self, query: str, top_k: int = 6):
        # 1. Embed query bằng OpenAI
        q_dense = self._embed_query_dense(query)
        
        # 2. Tính cosine similarity với documents
        dense_scores = cosine_similarity(q_dense, documents)
        
        # 3. TF-IDF matching
        sparse_scores = tfidf_similarity(query, documents)
        
        # 4. Kết hợp scores
        combined_score = 0.65 * dense_scores + 0.35 * sparse_scores
        
        # 5. Type boosting (issue > project > member)
        score *= type_boost
        
        # 6. Trả về top-k documents
        return top_k_results
```

### 2. Graph Structured Retriever

Tổ chức dữ liệu theo cấu trúc graph:

```
Project A
  ├── Tasks
  │   ├── Task 1
  │   └── Task 2
  └── Members
      ├── Member 1
      └── Member 2
```

**Lợi ích:**
- Trả về context có cấu trúc
- Hiển thị project cùng với tasks và members
- Dễ đọc hơn cho LLM

### 3. Luồng xử lý QA

```python
def handle_query(self, user_id: int, query: str):
    # 1. Fetch data từ Plane API
    data = self._fetch_rag_data(plane_api)
    # data = [projects, issues, members]
    
    # 2. Index data (embed + TF-IDF)
    self.rag.index_data(data)
    self.structured_rag.rebuild_graph(data)
    
    # 3. Retrieve relevant context
    context = self.structured_rag.retrieve_context(query, top_k=10)
    
    # 4. Generate answer với LLM
    prompt = PROMPT_QA_RAG.format(context=context, query=query)
    response = self.llm.generate_response(prompt)
    
    return response
```

---

## 💾 Memory Management

### Redis Memory

**File:** `src/auto_pm_agent_api/infrastructure/db/redis_memory.py`

Lưu trữ conversation history trong Redis:

```python
class RedisMemory:
    def add_message(self, user_id, role, content):
        key = f"chat_history:{user_id}"
        msg = json.dumps({"role": role, "content": content})
        self.redis.rpush(key, msg)
        self.redis.ltrim(key, -10, -1)  # Giữ 10 messages gần nhất
```

**Cấu trúc:**
- Key: `chat_history:{user_id}`
- Value: List of JSON messages
- Limit: 10 messages gần nhất

### Memory Retrieval

**File:** `src/auto_pm_agent_api/infrastructure/api/dependencies.py`

Hệ thống sử dụng simple memory retrieval - chỉ lấy N messages gần nhất:

```python
# Trong ChatService
selected_history = self.memory.get_history(user_id, limit=5)
```

**Lợi ích:**
- Đơn giản, không cần LLM call
- Giảm chi phí
- Đủ cho hầu hết các trường hợp sử dụng
- Không cần method `select_relevant_history` phức tạp

---

## 🔌 Plane API Client

**File:** `src/auto_pm_agent_api/infrastructure/plane_client/plane_api_client.py`

Client để tương tác với Plane.so API:

**Các methods chính:**
- `list_projects()` - Lấy danh sách projects
- `create_project()` - Tạo project mới
- `update_project()` - Cập nhật project
- `delete_project()` - Xóa project
- `list_issues()` - Lấy danh sách tasks
- `create_issue()` - Tạo task mới
- `update_issue()` - Cập nhật task
- `list_members()` - Lấy danh sách members
- `add_member_to_project()` - Thêm member vào project
- `remove_member_from_workspace()` - Xóa member

**Authentication:**
```python
headers = {
    "Authorization": f"Bearer {self.api_key}",
    "Content-Type": "application/json"
}
```

---

## 🧠 LLM Client

**File:** `src/auto_pm_agent_api/infrastructure/llm_providers/llm_client.py`

Wrapper cho OpenAI API:

**Features:**
- Structured output (Pydantic models)
- Retry logic
- Error handling
- Configurable base URL (hỗ trợ proxy)

**Usage:**
```python
llm = LLMClient()
response = llm.generate_response(prompt, output_format=IntentResult)
```

---

## 📊 Data Models

### Domain Models

**Plane Models:**
- `PlaneProject` - Project model
- `PlaneIssue` - Task/Issue model
- `PlaneMember` - Member model

**Report Models:**
- `WorkReportData` - Báo cáo công việc

### API Models

**Request:**
- `ChatRequest` - user_id, query, file_content
- `WorkReportExtractRequest` - content

**Response:**
- `ChatResponse` - user_id, query, response, success, error
- `WorkReportExtractResponse` - success, data, message, error

---

## 🔄 Luồng Dữ Liệu Hoàn Chỉnh

### Ví dụ: Tạo Project Mới

```
1. User gửi file
   POST /chat
   {
     "user_id": 123,
     "file_content": "Project: AI Chatbot\nTasks: ..."
   }
   ↓
2. ChatService.handle_query()
   - Lưu file_content vào session
   - Trả về: "Tôi đã đọc file..."
   ↓
3. User: "Tạo project từ file này"
   POST /chat
   {
     "user_id": 123,
     "query": "Tạo project từ file này"
   }
   ↓
4. ChatService.handle_query()
   - Intent classification: "create_new_project"
   - Route đến ProjectManagementService
   ↓
5. ProjectManagementService.handle_create_project()
   - Extract data từ file (LLM)
   - Validate data
   - Store in session
   - Trả về: "Tôi đã trích xuất project 'AI Chatbot' với 5 tasks. Bạn có muốn tạo không?"
   ↓
6. User: "Có"
   POST /chat
   {
     "user_id": 123,
     "query": "Có"
   }
   ↓
7. ProjectManagementService.handle_create_project()
   - Check confirmation
   - Create project on Plane
   - Create tasks
   - Clear session
   - Trả về: "Đã tạo project thành công!"
   ↓
8. Save to memory
   - memory.add_message(user_id, "user", "Có")
   - memory.add_message(user_id, "chatbot", "Đã tạo project thành công!")
```

---

## 🎨 Các Tính Năng Nổi Bật

### 1. Multi-Session Support
- Quản lý nhiều session đồng thời (mỗi user một session)
- Xử lý conflict khi user chuyển intent giữa chừng
- Nhắc nhở context khi user hỏi QA trong session

### 2. Smart Memory Selection
- Chỉ gửi lịch sử liên quan cho LLM
- Giảm token usage
- Tăng độ chính xác

### 3. Hybrid RAG
- Kết hợp dense + sparse retrieval
- Type boosting (issue > project > member)
- Graph-structured context

### 4. Intent Override
- Heuristic để sửa lỗi phân loại intent
- Ví dụ: "add member to project" → `update_existing_information` (không phải `assignment`)

### 5. Error Handling
- Graceful degradation
- Fallback mechanisms
- Detailed error messages

---

## 🔧 Configuration

**File:** `src/auto_pm_agent_api/config.py`

Cấu hình từ environment variables:

```python
class Settings:
    # LLM
    model_name: str = "gpt-3.5-turbo"
    api_key: Optional[str] = None
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    
    # Plane
    plane_api_key: Optional[str] = None
    plane_workspace_slug: Optional[str] = None
```

---

## 📝 Prompts

**File:** `src/auto_pm_agent_api/domain/prompts/templates.py`

Các prompt templates cho LLM:

1. **PROMPT_ROUTER** - Phân loại intent
2. **PROMPT_EXTRACT_UPDATE** - Trích xuất thông tin cập nhật
3. **PROMPT_QA_RAG** - Trả lời câu hỏi với RAG context

---

## 🚀 Deployment

**Docker:**
- `Dockerfile` - Container image
- `docker-compose.yaml` - Orchestration

**Dependencies:**
- `requirements.txt` - Python packages
- `pyproject.toml` - Project metadata

---

## 🧪 Testing

**Test files:**
- `test_api_endpoints.py` - API tests
- `test_chat_service.py` - Service tests
- `test_project_management_service.py` - Project service tests
- `test_qa_service.py` - QA service tests

---

## 📌 Tóm Tắt

Hệ thống này là một **AI-powered chatbot** phức tạp với:

1. **Clean Architecture** - Tách biệt rõ ràng các layers
2. **Multi-session management** - Xử lý các luồng dài
3. **RAG-based QA** - Trả lời câu hỏi chính xác
4. **LLM integration** - Hiểu ngôn ngữ tự nhiên
5. **Plane.so integration** - Quản lý projects/tasks thực tế
6. **Smart memory** - Chọn lọc context liên quan

Hệ thống có thể:
- ✅ Tạo/cập nhật/xóa projects và tasks
- ✅ Trả lời câu hỏi về projects/tasks
- ✅ Giao việc cho members
- ✅ Xử lý file upload
- ✅ Quản lý conversation history
- ✅ Xử lý multi-turn conversations

