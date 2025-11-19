# CODEBASE ANALYSIS: AI PM CHATBOT (Multi-Session System)

## PROJECT OVERVIEW

This is a FastAPI-based AI chatbot system designed to support project managers using the **Plane** project management tool. The system uses LLM (Large Language Models) with structured outputs to manage 4 distinct sessions/workflows.

**Tech Stack:**
- Backend: FastAPI + Python
- LLM: Google Gemini 2.0 Flash (via OpenRouter API)
- Memory: Redis (conversation history)
- API: Plane Project Management (REST API)
- Data Processing: Pydantic (structured outputs), requests (HTTP)

**Current Status:**
- Session 1: FULLY IMPLEMENTED (Create Project from file)
- Session 2: NOT IMPLEMENTED (QA with RAG)
- Session 3: PARTIALLY IMPLEMENTED (skeleton only)
- Session 4: PARTIALLY IMPLEMENTED (skeleton only)

---

## COMPLETE PROJECT STRUCTURE

```
/home/mtagi/Thang/AI_PM/Chatbotnew/
├── api.py                              # FastAPI application entry point (37 lines)
├── agent.py                            # Main Agent class orchestrating all logic (73 lines)
├── readme.md                           # Project requirements document
├── .env                                # Environment configuration
│
├── llm/                                # LLM Client Management
│   ├── llm_client.py                   # LLMClient - abstraction for LLM calls (27 lines)
│   ├── gemini.py                       # [Empty] Gemini-specific provider
│   └── openrouter.py                   # [Empty] OpenRouter provider
│
├── memory/                             # Conversation Memory Management
│   ├── __init__.py                     # Exports RedisMemory
│   └── redis_memory.py                 # RedisMemory class (50 lines)
│
├── utils/                              # Utility Bots & Routers
│   ├── __init__.py                     # Exports utilities
│   ├── router.py                       # Router class - intent classification (36 lines)
│   ├── memory_select_bot.py            # MemorySelectBot - relevant history selection (16 lines)
│   └── genaral_bot.py                  # GeneralBot - handle non-work topics (16 lines)
│
├── prompt/                             # Prompt Templates & Configuration
│   ├── utils/
│   │   ├── prompt_router.py            # Intent classification prompts (30 lines)
│   │   ├── prompt_memory_select.py     # History selection prompts (19 lines)
│   │   ├── prompt_genaral_bot.py       # General conversation prompts (25 lines)
│   │   └── prompt_plane_extract.py     # Older extraction prompt (34 lines)
│   └── session_create_project/
│       └── check_out_session.py        # [Empty]
│
├── session/                            # Session Management (Distinct Workflows)
│   ├── session_manager.py              # SessionManager - routes to specific sessions (20 lines)
│   ├── session_create_project/         # Session 1: Create Project from File
│   │   ├── session_create_project.py   # Main session handler (54 lines)
│   │   ├── plane_extractor.py          # PlaneExtractor - LLM extraction (53 lines)
│   │   ├── update_plane.py             # PlaneAPI - Plane REST API calls (143 lines)
│   │   ├── check.py                    # AffirmativeChecker - check user confirmation (81 lines)
│   │   ├── check_query.py              # [Empty]
│   │   └── prompt/
│   │       └── prompt_plane_extractor.py # Extraction prompts (37 lines)
│   │
│   ├── session_update_info.py          # Session 3: Update Info [SKELETON - 6 lines]
│   └── session_assignment.py           # Session 4: Task Assignment [SKELETON - 7 lines]
│
└── .claude/                            # Claude IDE configuration
    └── settings.local.json
```

**Total Python Code: 769 lines**

---

## ENVIRONMENT CONFIGURATION

**File:** `.env`

```env
API_KEY = "sk-or-v1-..."                # OpenRouter API key (LLM)
BASE_URL = "https://openrouter.ai/api/v1" # OpenRouter endpoint
MODEL_NAME = "google/gemini-2.0-flash-001" # Model selection
GOOGLE_API_KEY = "AIzaSyD_..."          # Google API key (fallback)
BASE_URL_PLANE = "https://711a4b14320a.ngrok-free.app" # Plane API endpoint (tunneled)
```

**Hardcoded Credentials (IN CODE - SECURITY RISK):**
- Session 1: `plane_api_49e5f398343f4a13a3aff4ad2318ad6f` (update_plane.py:19)
- Workspace: `workspace-mq`
- Demo credentials: `tung.0982548086@gmail.com` / `Tung20193177@`

---

## DATA MODELS & SCHEMAS

### ProjectSchema
```python
name: str                  # Project name
identifier: str            # 4-6 char code (uppercase, no diacritics)
description: Optional[str] # Short description
```

### TaskSchema
```python
name: str                  # Task name
description: Optional[str] # Task description/results
start_date: Optional[str]  # YYYY-MM-DD format
target_date: Optional[str] # YYYY-MM-DD format
```

### ExtractedPlaneData (Session 1 Output)
```python
is_info_project: bool      # True if content is valid project info
project: Optional[ProjectSchema]
tasks: Optional[List[TaskSchema]]
```

### AffirmativeResult (Confirmation Check)
```python
is_affirmative: bool       # True if user agreed
reason: Optional[str]      # Explanation
```

### IntentResult (Router Classification)
```python
intent: Literal[
    "create_new_project",
    "update_existing_information",
    "ask_about_existing_information",
    "update_plane_information",
    "other_topics"
]
```

---

## ARCHITECTURE & DATA FLOW

### Overall System Architecture

```
User Request (API.py:18-32)
    ↓
Agent.query() [agent.py:36-74]
    ↓
[1] Check if file content → Save & return confirmation
    ↓
[2] Get short-term memory from Redis
    ↓
[3] Route to appropriate handler:
    ├─→ Session (if active) → SessionManager.router_session()
    └─→ Intent Classification → Router.predict()
        ├─→ "create_new_project" → SessionCreateProject
        ├─→ "other_topics" → GeneralBot
        ├─→ "update_existing_information" → [TODO]
        └─→ "ask_about_existing_information" → [TODO]
    ↓
[4] Save conversation to Redis memory
    ↓
Response to User
```

### Session 1: Create Project from File (FULLY IMPLEMENTED)

**Flow:**
```
User uploads file
    ↓
SessionCreateProject.handle_session()
    ├─ Status: None
    │   ├─→ Check file content exists
    │   ├─→ PlaneExtractor.extract(file_content)
    │   │   └─→ LLMClient.generate_response(prompt, ExtractedPlaneData)
    │   └─→ Validate is_info_project flag
    │       ├─ If False → Ask for better file
    │       └─ If True → Set status="ready_to_create_project"
    │               Return: Show extracted project & ask confirmation
    │
    └─ Status: ready_to_create_project
        ├─→ AffirmativeChecker.check(user_response)
        │   └─→ LLMClient.generate_response(prompt, AffirmativeResult)
        ├─ If True → PlaneAPI.upload_project_with_tasks()
        │   ├─→ PlaneAPI.create_project(project)
        │   │   └─→ POST /api/v1/workspaces/{slug}/projects/
        │   └─→ PlaneAPI.create_task(project_id, task) [for each task]
        │       └─→ POST /api/v1/workspaces/{slug}/projects/{pid}/issues/
        └─ If False → Cancel & reset
```

**Key Classes:**

1. **PlaneExtractor** (plane_extractor.py:37-50)
   - Extract project data from any text/file content
   - Uses LLM with Pydantic structured output
   - Returns: ExtractedPlaneData

2. **AffirmativeChecker** (check.py:39-53)
   - Check if user confirmed the operation
   - Understands Vietnamese affirmation phrases
   - Returns: AffirmativeResult

3. **PlaneAPI** (update_plane.py:29-107)
   - REST API wrapper for Plane
   - Methods:
     - `create_project(name, identifier, description)` → POST /projects/
     - `create_task(project_id, task)` → POST /projects/{id}/issues/
     - `upload_project_with_tasks(project, tasks)` → Orchestrates both

---

## LLM INTEGRATION

### LLMClient (llm/llm_client.py)

```python
class LLMClient:
    def __init__(self):
        self.model_name = "google/gemini-2.0-flash-001"
        self.base_url = "https://openrouter.ai/api/v1"
        self.llm = init_chat_model(
            model=model_name,
            model_provider="openai",
            base_url=base_url
        )
    
    def generate_response(prompt, output_format=None):
        if output_format:  # Structured output (Pydantic schema)
            return llm.with_structured_output(output_format).invoke(prompt)
        else:  # Free-form text
            return llm.invoke(prompt).content
```

**Features:**
- Uses LangChain's `init_chat_model` abstraction
- Supports structured outputs via Pydantic schemas
- Currently: Google Gemini 2.0 Flash via OpenRouter

**Stub Provider Files:**
- `llm/gemini.py` - Empty (for future direct Gemini API)
- `llm/openrouter.py` - Empty (for future direct OpenRouter)

---

## PROMPT ENGINEERING

### 1. Intent Classification (prompt_router.py:1-30)
**Purpose:** Classify user query into 5 categories
**Categories:**
- "create_new_project" - User wants to create project
- "update_existing_information" - User wants to modify data
- "ask_about_existing_information" - User asking questions
- "other_topics" - Non-work related

### 2. Plane Data Extraction (prompt_plane_extractor.py:1-37)
**Purpose:** Extract project & task data from file/text
**Input:** Raw file content (JSON, text, etc.)
**Output:** ExtractedPlaneData JSON
**Key Instructions:**
- Mark `is_info_project=true/false`
- Extract project name, identifier, description
- Extract tasks with dates in YYYY-MM-DD format
- Return pure JSON, no markdown code blocks

### 3. Affirmative Checking (check.py:8-27)
**Purpose:** Detect if user agreed to operation
**Vietnamese Keywords:** "đúng", "ok", "vâng", "dạ", "yes", "đồng ý"
**Output:** is_affirmative boolean + reason

### 4. Memory Selection (prompt_memory_select.py:3-19)
**Purpose:** Extract relevant conversation history
**Input:** Full history + current question
**Output:** Filtered relevant messages only

### 5. General Conversation (prompt_genaral_bot.py:1-25)
**Purpose:** Handle non-work topics naturally
**Style:** Friendly, conversational, no labels
**Input:** History + question
**Output:** Natural language response

---

## MEMORY MANAGEMENT

### RedisMemory (memory/redis_memory.py)

```python
class RedisMemory:
    def __init__(self, host='localhost', port=6379, db=0):
        self.redis = Redis(host, port, db)
        self.max_messages = 10  # Keep last 10 messages
    
    def add_message(user_id, role, content):
        # Store: {"role": "user"/"chatbot", "content": text}
        # Key: chat_history:{user_id}
    
    def get_history(user_id):
        # Return: [{"role": "user", "content": "..."}, ...]
        # Fallback: fetch_history_from_api() if empty
```

**Features:**
- Per-user conversation history
- Auto-trimmed to 10 most recent messages
- JSON serialization
- Fallback to external API if Redis empty

---

## UTILITY BOTS & ROUTERS

### Router (utils/router.py)

```python
class Router:
    def predict(selected_history, query) -> str:
        # Input: Conversation history + current query
        # Process: Send to LLM with PROPMT_ROUTER
        # Output: One of 5 intents
```

### MemorySelectBot (utils/memory_select_bot.py)

```python
class MemorySelectBot:
    def get_memory_select(history, query) -> str:
        # Extract relevant conversation turns
        # Reduces context size for LLM
```

### GeneralBot (utils/genaral_bot.py)

```python
class GenaralBot:
    def gen_response(selected_history, query) -> str:
        # Generate natural response for non-work topics
        # Uses GENERAL_BOT_PROMPT template
```

---

## PLANE API INTEGRATION

### PlaneAPI Class (update_plane.py:29-107)

**Base Configuration:**
```python
BASE_URL = "{BASE_URL_PLANE}/api/v1/workspaces/{workspace_slug}"
Headers: {
    "x-api-key": api_key,
    "Content-Type": "application/json"
}
```

**Implemented Endpoints:**

1. **Create Project**
   ```
   POST /projects/
   Payload:
   {
     "name": "Project Name",
     "identifier": "PROJ",
     "description": "...",
     "network": 2,
     "is_deployed": true
   }
   Response: Project object with id
   ```

2. **Create Task/Issue**
   ```
   POST /projects/{project_id}/issues/
   Payload:
   {
     "name": "Task Name",
     "description": "...",
     "start_date": "YYYY-MM-DD",
     "target_date": "YYYY-MM-DD"
   }
   Response: Issue object
   ```

**TODO (Not Implemented):**
- Get project details
- Get task details
- Update task (for Session 3)
- Assign task to user (for Session 4)
- Get members list
- Get task status values
- Filter by status/priority/assignee

---

## SESSION MANAGER & ROUTER

### SessionManager (session/session_manager.py)

```python
class SessionManager:
    def __init__(self, llm_client):
        self.session_create_project = SessionCreateProject(llm_client)
        # TODO: session_update_info
        # TODO: session_assignment
    
    def router_session(user_id, intent, query, file_content, history):
        if intent == "create_new_project":
            return SessionCreateProject.handle_session()
        # TODO: elif intent == "update_existing_information"
        # TODO: elif intent == "assignment"
```

**Current Sessions:**
1. ✅ `SessionCreateProject` - FULLY IMPLEMENTED
2. ❌ `SessionUpdateInfo` - SKELETON ONLY (session_update_info.py:1-7)
3. ❌ `SessionAssignment` - SKELETON ONLY (session_assignment.py:1-7)

---

## FASTAPI APPLICATION (api.py)

```python
@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    # Input schema:
    # {
    #   "user_id": int,
    #   "query": Optional[str],
    #   "file_content": Optional[str],
    #   "long_memory": Optional[str]
    # }
    
    # Returns:
    # {
    #   "user_id": int,
    #   "query": str,
    #   "response": str
    # }

@app.get("/")
def root():
    return {"message": "ChatBot API is running"}
```

**Global Agent Instance:**
- Single `Agent()` instance reused across requests
- Uses Redis for per-user memory
- Maintains session state

---

## KEY FINDINGS & GAPS

### IMPLEMENTED WELL:
1. ✅ Session 1 (Create Project) - Production ready with confirmation flow
2. ✅ LLM abstraction via LangChain
3. ✅ Structured outputs via Pydantic
4. ✅ Redis memory management
5. ✅ Intent routing architecture
6. ✅ Plane API wrapper (basic CRUD)
7. ✅ Affirmative checking
8. ✅ Prompt templates

### MISSING/TODO FOR SESSION 2 (QA with RAG):
1. ❌ Vector database integration (Qdrant/Chroma not installed)
2. ❌ Embedding model for RAG
3. ❌ Document chunking strategy
4. ❌ Data indexing from Plane
5. ❌ RAG query pipeline
6. ❌ Session 2 handler class
7. ❌ Plane GET endpoints (fetch projects, tasks, members)

### MISSING/TODO FOR SESSION 3 (Update Info):
1. ❌ Session handler implementation (skeleton at session_update_info.py)
2. ❌ Information extraction prompt
3. ❌ Validation logic (check missing fields)
4. ❌ Interactive confirmation flow
5. ❌ Plane API UPDATE/PATCH endpoints
6. ❌ Field mapping (user input → Plane API fields)

### MISSING/TODO FOR SESSION 4 (Task Assignment):
1. ❌ Session handler implementation (skeleton at session_assignment.py)
2. ❌ Assignment logic prompt
3. ❌ Load calculation (tasks per member)
4. ❌ Skill matching
5. ❌ Member workload assessment
6. ❌ Plane API ASSIGN endpoints
7. ❌ Member list retrieval

### SECURITY ISSUES:
1. ⚠️ Hardcoded API keys in code (session_create_project.py:19)
2. ⚠️ Demo credentials in response message
3. ⚠️ .env file in git (if version controlled)
4. ⚠️ No authentication on /chat endpoint

### CODE QUALITY:
1. ⚠️ Typo: "Genaral" instead of "General" throughout
2. ⚠️ Empty stub files (check_query.py, check_out_session.py, gemini.py, openrouter.py)
3. ⚠️ Mixed Vietnamese/English comments
4. ⚠️ No input validation on ChatRequest
5. ⚠️ Limited error handling in API calls
6. ⚠️ Unused parameter `long_memory` in chat endpoint

### DEPENDENCIES (Implied from imports):
- fastapi
- pydantic
- redis
- requests
- python-dotenv
- langchain
- openai (for init_chat_model)

---

## RECOMMENDATIONS FOR SESSIONS 2, 3, 4

### Session 2: QA with RAG
**Architecture:**
1. Add vector DB: Install `qdrant-client` or `chromadb`
2. Create RAG Pipeline:
   - Fetch project data from Plane API
   - Chunk documents (projects, tasks, comments)
   - Generate embeddings (use OpenAI or open-source)
   - Store in vector DB with metadata
3. Query Handler:
   - Convert user question to embedding
   - Retrieve relevant documents
   - Generate answer with LLM + context
4. Session Class: `SessionQA`

### Session 3: Update Information
**Architecture:**
1. Create extractor for update requests
   - Identify: task/project, field, old value, new value
2. Validation layer
   - Check if missing required fields
   - Ask user for clarification
3. Confirmation flow
   - Show extracted data
   - Get user approval
4. Plane API Methods:
   - PATCH /issues/{id}/ - update task
   - PATCH /projects/{id}/ - update project
5. Session Class: `SessionUpdateInfo`

### Session 4: Task Assignment
**Architecture:**
1. Assessment engine
   - Fetch members + current workload
   - Calculate: task count, priority, deadline
   - Extract: skill requirements from tasks
2. LLM Assignment Prompt
   - Input: tasks list + members + workload
   - Output: assignment recommendations
3. Confirmation & execution
   - Show assignments
   - Get approval
   - Update via Plane API
4. Plane API Methods:
   - PATCH /issues/{id}/ - assign task (update assignees field)
   - GET /workspaces/{slug}/members/ - fetch team
   - GET /projects/{id}/issues/ - get all tasks
5. Session Class: `SessionAssignment`

---

## FILE MANIFEST WITH RESPONSIBILITIES

| File | Lines | Purpose |
|------|-------|---------|
| api.py | 37 | FastAPI app, /chat endpoint |
| agent.py | 73 | Main orchestrator, memory + routing |
| llm/llm_client.py | 27 | LLM abstraction wrapper |
| memory/redis_memory.py | 50 | Redis conversation storage |
| utils/router.py | 36 | Intent classification |
| utils/memory_select_bot.py | 16 | Relevant history extraction |
| utils/genaral_bot.py | 16 | General topic responses |
| session/session_manager.py | 20 | Route to sessions |
| session/session_create_project/session_create_project.py | 54 | Session 1 handler |
| session/session_create_project/plane_extractor.py | 53 | Extract via LLM |
| session/session_create_project/update_plane.py | 143 | Plane API client |
| session/session_create_project/check.py | 81 | Affirmative detection |
| prompt/utils/*.py | 104 | LLM prompts |
| session/session_update_info.py | 6 | Session 3 [SKELETON] |
| session/session_assignment.py | 7 | Session 4 [SKELETON] |

