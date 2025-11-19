# QUICK START: Understanding the Codebase

## 5-Minute Overview

This is a **4-Session AI Chatbot** for managing Plane projects:

```
Session 1 (✅ DONE): "Create project from file"
  User uploads file → LLM extracts data → Creates project in Plane

Session 2 (❌ TODO): "Ask questions with RAG"
  User asks "How many tasks in AI2School?" → Vector search + LLM → Answer

Session 3 (❌ TODO): "Update information"
  User: "Change deadline to 30/11" → Extract → Validate → Update in Plane

Session 4 (❌ TODO): "Assign tasks intelligently"
  User: "Assign 10 tasks" → Check workload → Recommend → Assign in Plane
```

**Tech: FastAPI + Redis + OpenRouter LLM + Plane API + Pydantic**

---

## Key Files to Understand First

### 1. Main Entry Point
**`api.py`** - FastAPI app with single `/chat` endpoint
- Takes: user_id, query, file_content
- Returns: chatbot response

**`agent.py`** - The orchestrator
- Gets memory from Redis
- Routes to right handler (session/intent)
- Saves conversation to Redis

### 2. Session 1 Implementation (Study This Pattern!)
**`session/session_create_project/`** - Complete example of a multi-turn session
- `session_create_project.py` - State machine (status: None → extracted → confirmed)
- `plane_extractor.py` - Uses LLM to extract JSON from file
- `check.py` - Uses LLM to check if user confirmed
- `update_plane.py` - REST API wrapper for Plane

### 3. Routing
**`utils/router.py`** - Intent classification (which session to use)
**`session/session_manager.py`** - Route to correct session based on intent

### 4. Memory
**`memory/redis_memory.py`** - Stores last 10 messages per user

### 5. LLM
**`llm/llm_client.py`** - Wrapper around OpenRouter + Google Gemini

---

## How Session 1 Works (The Complete Pattern)

```
1. User uploads file
   └─ Agent saves file content, returns: "File received"

2. Next message: User says anything
   └─ Router classifies intent → "create_new_project"
   └─ SessionCreateProject.handle_session() called with status=None
   
3. In SessionCreateProject (status=None):
   ├─ Call PlaneExtractor.extract(file_content)
   │  └─ LLM + PROMPT → ExtractedPlaneData JSON
   │     (has: is_info_project flag, project details, task list)
   │
   ├─ Check is_info_project flag
   │  ├─ If False: Reject + ask for better file
   │  └─ If True: Set status="ready_to_create_project"
   │             Return: "I found a project. Create it?" (show details)

4. User confirms next message
   └─ Router → SessionCreateProject.handle_session() with status="ready_to_create_project"

5. In SessionCreateProject (status=ready_to_create_project):
   ├─ Call AffirmativeChecker.check(user_response)
   │  └─ LLM checks: is user saying yes? (Vietnamese aware)
   │
   ├─ If Yes:
   │  └─ PlaneAPI.upload_project_with_tasks()
   │     ├─ POST /projects/ → Creates project, gets project_id
   │     └─ POST /issues/ (for each task) → Creates tasks
   │     └─ Return: Success URL
   │
   └─ If No: Cancel, status reset to None

6. Reset state=None, ready for next session
```

**Key: State Machine Pattern** - Uses `self.status` to track multi-turn conversation

---

## How to Implement Session 2 (QA with RAG)

### Step 1: What You Need
- Vector database (Qdrant or Chroma)
- Embedding model (HuggingFace)
- Fetch Plane data (projects, tasks, members)

### Step 2: Files to Create
```
session/
├── session_qa.py                    # Handler (NEW)
└── rag/
    ├── rag_pipeline.py              # Vector DB + embeddings (NEW)
    └── plane_data_fetcher.py        # Fetch from Plane API (NEW)

prompt/session_qa/
└── prompt_qa.py                     # LLM prompt (NEW)
```

### Step 3: Code Structure
```python
class SessionQA:
    def handle_session(self, user_id, query, ...):
        # 1. Fetch latest Plane data
        data = self.fetcher.fetch_all_data()
        
        # 2. Index into vector DB
        self.rag.index(data)
        
        # 3. Search for context
        context = self.rag.query(query)
        
        # 4. Generate answer with LLM
        response = self.llm.generate_response(
            prompt + context,
            output_format=None  # Free text, not JSON
        )
        
        return "session_qa", response
```

---

## How to Implement Session 3 (Update Info)

### Step 1: Files to Create
```
session/session_update_info/
└── update_extractor.py              # Extract update request (NEW)

prompt/session_update_info/
└── prompt_update_extract.py         # LLM prompt (NEW)
```

### Step 2: State Machine
```python
class SessionUpdateInfo:
    status = None → Extract update → Show summary → Confirm → Update Plane
```

### Step 3: New Plane API Methods Needed
```python
class PlaneAPI:
    def get_task(project_id, task_id) → Fetch task details
    def update_task(project_id, task_id, updates) → PATCH /issues/
    def get_project(project_id) → Fetch project
    def update_project(project_id, updates) → PATCH /projects/
    def search_task(project_id, query) → Find task by name
```

---

## How to Implement Session 4 (Task Assignment)

### Step 1: Files to Create
```
session/session_assignment/
├── workload_assessor.py             # Calculate member load (NEW)
└── assignment_strategy.py           # LLM-based assignment (NEW)

prompt/session_assignment/
└── prompt_assignment.py             # LLM prompt (NEW)
```

### Step 2: Logic
```
Fetch: Unassigned tasks + team members + workload
  ↓
LLM analyzes: Task complexity + member capacity + skills
  ↓
Returns: Assignments with reasoning
  ↓
User confirms → PATCH /issues/ with assignees field
```

### Step 3: New Plane API Methods Needed
```python
class PlaneAPI:
    def get_members(workspace_slug) → Fetch all team members
    def get_unassigned_tasks(project_id) → Tasks without assignee
    def assign_task(project_id, task_id, member_id) → PATCH with assignees
```

---

## Common Patterns to Reuse

### Pattern 1: LLM with Structured Output
```python
from pydantic import BaseModel

class MyOutput(BaseModel):
    field1: str
    field2: bool

result = self.llm.generate_response(prompt, MyOutput)
# Returns: MyOutput instance with validated fields
```

### Pattern 2: Session State Machine
```python
class MySession:
    def __init__(self):
        self.status = None  # Track state
    
    def handle_session(self, user_id, query, ...):
        if self.status is None:
            # First interaction
            self.status = "step_2"
            return "my_session", "Here's what I found. Confirm?"
        
        elif self.status == "step_2":
            # Second interaction
            self.status = None  # Reset
            return None, "Done!"
```

### Pattern 3: Confirmation Flow
```python
affirmative = AffirmativeChecker(llm).check(user_response)
if str(affirmative.is_affirmative).lower() == "true":
    # Do the thing
    pass
else:
    # Cancel
    pass
```

### Pattern 4: Plane API CRUD
```python
# Create
response = requests.post(url, json=payload, headers=headers)
if response.status_code in (200, 201):
    return response.json()

# Update
response = requests.patch(url, json=updates, headers=headers)
if response.status_code in (200, 204):
    return True

# Search
results = [item for item in all_items if query.lower() in item['name'].lower()]
```

---

## Testing Your Implementation

### Session 1 (Already Works)
```python
# 1. Upload file
response = client.post("/chat", json={
    "user_id": 1,
    "file_content": "JSON content here..."
})
# Response: "File received"

# 2. Ask to create
response = client.post("/chat", json={
    "user_id": 1,
    "query": "create project"
})
# Response: "Here's what I found. Create it?"

# 3. Confirm
response = client.post("/chat", json={
    "user_id": 1,
    "query": "yes"
})
# Response: "Success! Project created..."
```

### Session 2 (WIP)
```python
response = client.post("/chat", json={
    "user_id": 1,
    "query": "How many tasks in AI2School?"
})
# Response: "AI2School has 5 tasks..."
```

### Session 3 (WIP)
```python
response = client.post("/chat", json={
    "user_id": 1,
    "query": "Set deadline of task X to 30/11"
})
# Response: "I'll update task X deadline to 30/11. Confirm?"
```

### Session 4 (WIP)
```python
response = client.post("/chat", json={
    "user_id": 1,
    "query": "Assign 10 unassigned tasks"
})
# Response: "Here's my recommendation: A→4 tasks, B→3 tasks, C→3 tasks. Confirm?"
```

---

## Environment Setup

**Required in `.env`:**
```
API_KEY=sk-or-...                              # OpenRouter
BASE_URL=https://openrouter.ai/api/v1         # OpenRouter endpoint
MODEL_NAME=google/gemini-2.0-flash-001        # Model to use
BASE_URL_PLANE=https://your-plane-instance/   # Plane API
```

**Redis:**
- Must be running on localhost:6379
- Or change in `memory/redis_memory.py`

**Dependencies:**
```bash
pip install fastapi pydantic redis requests python-dotenv langchain openai
# For Session 2: add qdrant-client chromadb sentence-transformers
```

---

## Important Notes

1. **Hardcoded Credentials**: API keys are in code (session_create_project.py:19) - move to .env!

2. **Typo**: "Genaral" instead of "General" throughout - can fix in cleanup

3. **Empty Files**: check_query.py, check_out_session.py are empty - delete or fill

4. **Single Agent Instance**: All users share same Agent - fine for MVP, not for production

5. **No Error Handling**: Wrap Agent.query() in try-except

6. **Vietnamese-First**: Comments and prompts mostly in Vietnamese - keep for consistency

---

## Next Steps

1. **Read** `CODEBASE_ANALYSIS.md` - Full structure
2. **Study** Session 1 implementation in `session/session_create_project/`
3. **Follow** `IMPLEMENTATION_GUIDE.md` for Sessions 2, 3, 4
4. **Check** `ARCHITECTURE_DIAGRAMS.md` for visual flows
5. **Test** as you build each session
6. **Fix** security issues (hardcoded credentials)

---

## Support Materials Generated

1. **CODEBASE_ANALYSIS.md** - Complete codebase breakdown
2. **ARCHITECTURE_DIAGRAMS.md** - Visual system diagrams
3. **IMPLEMENTATION_GUIDE.md** - Detailed implementation steps
4. **QUICK_START.md** - This file

All files saved to `/home/mtagi/Thang/AI_PM/Chatbotnew/`

