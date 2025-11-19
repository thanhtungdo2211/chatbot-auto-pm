# IMPLEMENTATION GUIDE: Sessions 2, 3, and 4

## Quick Reference: What's Already Done vs What's Needed

### Session 1: CREATE PROJECT (100% Complete)
```
✅ PlaneExtractor class - extracts project data from files
✅ AffirmativeChecker class - checks user confirmation  
✅ PlaneAPI class - creates projects and tasks
✅ Session state machine - handles multi-turn workflow
✅ Error handling - checks is_info_project flag
✅ Redis memory - stores conversation history
✅ LLMClient integration - structured outputs with Pydantic

Files to study:
- session/session_create_project/session_create_project.py
- session/session_create_project/plane_extractor.py
- session/session_create_project/update_plane.py
- session/session_create_project/check.py
```

---

## SESSION 2: QA WITH RAG (RAG-Based Question Answering)

### Overview
Users ask questions about existing Plane projects, and the bot retrieves relevant information using vector similarity search + LLM generation.

### Architecture Decisions Needed

#### 1. Vector Database Choice
**Option A: Qdrant (Recommended)**
```
Pros:
- REST/gRPC API (no local dependency)
- Better for production
- Supports vector filters + metadata

Installation:
pip install qdrant-client

Code example:
from qdrant_client import QdrantClient
client = QdrantClient("localhost", port=6333)
```

**Option B: Chroma**
```
Pros:
- Lightweight, in-memory capable
- Easy to get started
- Good for prototyping

Installation:
pip install chromadb
```

**RECOMMENDATION:** Use Qdrant for scalability, but start with Chroma for quick prototyping.

#### 2. Embedding Model Choice
**Option A: OpenAI Embeddings (Current LLM provider)**
```python
from langchain_openai import OpenAIEmbeddings
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)
```

**Option B: Open-Source (Recommended for cost)**
```python
from langchain_community.embeddings import HuggingFaceEmbeddings
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
```

**RECOMMENDATION:** Use HuggingFace for cost savings. Size: 384 dimensions.

#### 3. Document Chunking Strategy
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,      # Tokens per chunk
    chunk_overlap=50,    # Overlap between chunks
    separators=["\n\n", "\n", " ", ""]
)
```

### Implementation Steps

#### Step 1: Create RAG Pipeline Module
**File:** `session/rag/rag_pipeline.py`

```python
from typing import List, Dict
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

class RAGPipeline:
    def __init__(self, vector_db_path="./qdrant_storage"):
        """Initialize embeddings and vector DB"""
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.client = QdrantClient(path=vector_db_path)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )
        self.collection_name = "plane_data"
        self._init_collection()
    
    def _init_collection(self):
        """Create Qdrant collection if not exists"""
        try:
            self.client.get_collection(self.collection_name)
        except:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=384,  # Dimension for all-MiniLM-L6-v2
                    distance=Distance.COSINE
                )
            )
    
    def index_project_data(self, project_id: str, data: Dict):
        """Index project data (project + tasks + members) into vector DB"""
        # 1. Create document chunks from project data
        documents = self._create_documents(project_id, data)
        
        # 2. Generate embeddings for each chunk
        # 3. Store in Qdrant with metadata
        pass
    
    def query(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search for relevant documents"""
        # 1. Embed query
        # 2. Search in Qdrant
        # 3. Return top-k results with scores
        pass
```

#### Step 2: Fetch Plane Data for Indexing
**File:** `session/rag/plane_data_fetcher.py`

```python
class PlaneDataFetcher:
    def __init__(self, api_key: str, workspace_slug: str):
        self.plane_api = PlaneAPI(api_key, workspace_slug)
    
    def fetch_all_data(self) -> Dict:
        """Fetch all projects, tasks, and members"""
        return {
            "projects": self.fetch_projects(),
            "tasks": self.fetch_all_tasks(),
            "members": self.fetch_members(),
            "comments": self.fetch_all_comments()
        }
    
    def fetch_projects(self) -> List[Dict]:
        """GET /projects/ - list all projects"""
        url = f"{self.plane_api.base_url}/projects/"
        response = requests.get(url, headers=self.plane_api.headers)
        return response.json() if response.status_code == 200 else []
    
    def fetch_all_tasks(self) -> List[Dict]:
        """GET /projects/{id}/issues/ - list all tasks per project"""
        # Loop through projects and fetch their tasks
        pass
    
    def fetch_members(self) -> List[Dict]:
        """GET /workspaces/{slug}/members/ - list team members"""
        url = f"{self.plane_api.base_url.rsplit('/api', 1)[0]}/members/"
        pass
```

#### Step 3: Create Session 2 Handler
**File:** `session/session_qa.py` (NEW FILE)

```python
from session.rag.rag_pipeline import RAGPipeline
from session.rag.plane_data_fetcher import PlaneDataFetcher

class SessionQA:
    """Session 2: Question Answering with RAG"""
    
    def __init__(self, llm_client, plane_api_key, workspace_slug):
        self.llm = llm_client
        self.rag = RAGPipeline()
        self.fetcher = PlaneDataFetcher(plane_api_key, workspace_slug)
    
    def handle_session(self, user_id, query, file_content, selected_history):
        """
        Flow:
        1. Fetch latest Plane data (or use cache if recent)
        2. Index into vector DB
        3. Search for relevant context
        4. Generate answer with LLM
        """
        
        # 1. Fetch and index data
        plane_data = self.fetcher.fetch_all_data()
        self.rag.index_project_data("workspace", plane_data)
        
        # 2. Retrieve context
        context = self.rag.query(query, top_k=5)
        
        # 3. Generate answer with LLM
        prompt = PROMPT_QA.format(
            context=context,
            query=query,
            history=selected_history or ""
        )
        
        response = self.llm.generate_response(prompt)
        return "session_qa", response
```

#### Step 4: Add Prompts for Session 2
**File:** `prompt/session_qa/prompt_qa.py` (NEW FILE)

```python
PROMPT_QA = """
Bạn là một trợ lý AI chuyên trả lời câu hỏi về các dự án Plane.

Dưới đây là bối cảnh từ cơ sở dữ liệu Plane:
===
{context}
===

Lịch sử hội thoại:
===
{history}
===

Câu hỏi của người dùng:
===
{query}
===

🎯 Nhiệm vụ:
1. Sử dụng bối cảnh được cung cấp để trả lời câu hỏi chính xác
2. Nếu thông tin không có sẵn, hãy nói rõ "Tôi không có thông tin này"
3. Trả về câu trả lời tự nhiên, thân thiện

Trả về: Câu trả lời tự nhiên (không JSON)
"""
```

#### Step 5: Update SessionManager
**File:** `session/session_manager.py` (MODIFY)

```python
from session.session_qa import SessionQA

class SessionManager:
    def __init__(self, llm_client):
        self.session_create_project = SessionCreateProject(llm_client)
        self.session_qa = SessionQA(llm_client, api_key, workspace_slug)  # ADD THIS
        # TODO: self.session_update_info
        # TODO: self.session_assignment
    
    def router_session(self, user_id, intent, query, file_content, selected_history):
        if intent == "create_new_project":
            return self.session_create_project.handle_session(...)
        elif intent == "ask_about_existing_information":  # ADD THIS
            return self.session_qa.handle_session(...)
```

### Dependencies to Add
```bash
pip install qdrant-client langchain-text-splitters sentence-transformers
# OR: pip install chromadb  (if using Chroma instead)
```

### Testing Session 2
```python
# Test query
response = session_qa.handle_session(
    user_id=1,
    query="Trong project AI2School còn bao nhiêu task chưa làm?",
    file_content=None,
    selected_history=None
)
```

---

## SESSION 3: UPDATE INFORMATION (Intelligent Info Updates)

### Overview
Users request to update project/task information. Bot extracts the update request, validates it, asks for confirmation, then updates Plane.

### Flow
```
User: "Cập nhật deadline của task Viết API sang 30/11"
    ↓
Extract: {task: "Viết API", field: "deadline", new_value: "2025-11-30"}
    ↓
Check if all required fields present
    ├─ If missing → Ask user to clarify
    └─ If complete → Show summary & ask confirmation
    ↓
User confirms → PATCH /issues/{id}/ → Success
```

### Implementation Steps

#### Step 1: Create Update Extractor
**File:** `session/session_update_info/update_extractor.py` (NEW FILE)

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class UpdateRequest(BaseModel):
    entity_type: str = Field(..., description="'task' or 'project'")
    entity_identifier: str = Field(..., description="Task/project name or ID")
    field: str = Field(..., description="Field to update (name, description, deadline, priority, state, etc.)")
    new_value: str = Field(..., description="New value for the field")
    old_value: Optional[str] = Field(None, description="Current/old value (optional, for confirmation)")

class UpdateExtractionResult(BaseModel):
    success: bool
    updates: Optional[List[UpdateRequest]] = None
    missing_info: Optional[List[str]] = None  # What info is missing
    clarification_needed: Optional[str] = None  # Question to ask user

class UpdateExtractor:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def extract(self, query: str) -> UpdateExtractionResult:
        """Extract update request from user query"""
        prompt = PROMPT_UPDATE_EXTRACT + query
        return self.llm.generate_response(prompt, UpdateExtractionResult)
```

#### Step 2: Add Plane Update API Methods
**File:** `session/session_create_project/update_plane.py` (MODIFY)

```python
class PlaneAPI:
    # ... existing methods ...
    
    # NEW METHODS FOR SESSION 3:
    
    def get_task(self, project_id: str, task_id: str):
        """GET /projects/{project_id}/issues/{task_id}/"""
        url = f"{self.base_url}/projects/{project_id}/issues/{task_id}/"
        response = requests.get(url, headers=self.headers)
        return response.json() if response.status_code == 200 else None
    
    def update_task(self, project_id: str, task_id: str, updates: Dict):
        """PATCH /projects/{project_id}/issues/{task_id}/"""
        url = f"{self.base_url}/projects/{project_id}/issues/{task_id}/"
        response = requests.patch(url, json=updates, headers=self.headers)
        if response.status_code in (200, 204):
            print(f"✅ Updated task {task_id}")
            return True
        else:
            print(f"❌ Failed to update: {response.status_code} - {response.text}")
            return False
    
    def search_task(self, project_id: str, query: str) -> Optional[str]:
        """Search for task by name and return task_id"""
        # Fuzzy match task name from project
        # Return best matching task_id
        pass
    
    def get_project(self, project_id: str):
        """GET /projects/{project_id}/"""
        pass
    
    def update_project(self, project_id: str, updates: Dict):
        """PATCH /projects/{project_id}/"""
        pass
```

#### Step 3: Create Session 3 Handler
**File:** `session/session_update_info.py` (REWRITE)

```python
from session.session_update_info.update_extractor import (
    UpdateExtractor, 
    UpdateExtractionResult,
    UpdateRequest
)
from session.session_create_project.update_plane import PlaneAPI
from session.session_create_project.check import AffirmativeChecker

class SessionUpdateInfo:
    """Session 3: Update Project/Task Information"""
    
    def __init__(self, llm_client, api_key, workspace_slug):
        self.llm = llm_client
        self.extractor = UpdateExtractor(llm_client)
        self.plane_api = PlaneAPI(api_key, workspace_slug)
        self.checker = AffirmativeChecker(llm_client)
        
        self.status = None  # None, "extracted", "confirmed"
        self.pending_updates = None
        self.project_id = None
    
    def handle_session(self, user_id, query, file_content, selected_history):
        if self.status is None:
            # Extract update request
            extraction = self.extractor.extract(query)
            
            if not extraction.success or extraction.missing_info:
                # Ask for clarification
                msg = extraction.clarification_needed or \
                      f"Bạn cần cung cấp: {', '.join(extraction.missing_info)}"
                return "session_update_info", msg
            
            # Show what we're about to update
            self.pending_updates = extraction.updates
            self.status = "extracted"
            
            summary = self._format_update_summary(extraction.updates)
            return "session_update_info", f"Tôi sẽ cập nhật:\n{summary}\n\nBạn có đồng ý không?"
        
        elif self.status == "extracted":
            # Check confirmation
            affirmative = self.checker.check(query)
            
            if str(affirmative.is_affirmative).lower() == "true":
                # Perform updates
                success = self._perform_updates()
                self.status = None
                self.pending_updates = None
                
                if success:
                    return "session_update_info", "✅ Cập nhật thành công!"
                else:
                    return "session_update_info", "❌ Lỗi cập nhật. Vui lòng thử lại."
            else:
                # Cancel
                self.status = None
                self.pending_updates = None
                return "session_update_info", "Đã hủy. Bạn cần gì khác?"
    
    def _format_update_summary(self, updates):
        """Format updates for display"""
        lines = []
        for update in updates:
            lines.append(f"- {update.entity_identifier}: {update.field} → {update.new_value}")
        return "\n".join(lines)
    
    def _perform_updates(self):
        """Actually perform the Plane API updates"""
        # TODO: Implement based on pending_updates
        pass
```

#### Step 4: Add Prompts for Session 3
**File:** `prompt/session_update_info/prompt_update_extract.py` (NEW FILE)

```python
PROMPT_UPDATE_EXTRACT = """
Bạn là một trợ lý AI chuyên trích xuất yêu cầu cập nhật dữ liệu từ người dùng.

🎯 Nhiệm vụ:
Phân tích câu yêu cầu của người dùng và trích xuất:
1. Entity (task hay project?)
2. Entity identifier (tên hoặc ID)
3. Field cần cập nhật
4. New value
5. Old value (nếu mentioned)
6. Missing information (nếu có)

📤 Định dạng kết quả:

Nếu trích xuất thành công:
{
  "success": true,
  "updates": [
    {
      "entity_type": "task",
      "entity_identifier": "Viết API Quiz",
      "field": "target_date",
      "new_value": "2025-11-30",
      "old_value": null
    }
  ],
  "missing_info": null
}

Nếu thiếu thông tin:
{
  "success": false,
  "updates": null,
  "missing_info": ["field"],
  "clarification_needed": "Bạn muốn cập nhật trường nào?"
}

⚠️ Lưu ý:
- Tên field: name, description, target_date, start_date, priority, state, assignees
- Dates phải dạng YYYY-MM-DD
- Priority: low, medium, high, urgent
- State: backlog, todo, in_progress, in_review, done

--- Yêu cầu người dùng ---
"""
```

#### Step 5: Update SessionManager
Already showed above - add SessionUpdateInfo import and router.

### Dependencies
```bash
# No new dependencies needed (use existing)
```

---

## SESSION 4: TASK ASSIGNMENT (Intelligent Workload Balancing)

### Overview
Distribute unassigned tasks among team members based on:
- Current workload (how many tasks each person has)
- Task complexity/priority
- Member skills (extracted from past task assignments)
- Deadline urgency

### Flow
```
User: "Giao 10 task mới cho project AI2School"
    ↓
Fetch:
- Unassigned tasks (10)
- Team members + current load
- Member skills (from past tasks)
    ↓
LLM Analysis:
"Member A: 3 tasks (all high-priority)
 Member B: 1 task (easy)
 Task 1-3: High complexity → A (but overloaded)
 Task 4-6: Medium → B (available)
 Task 7-10: Low → A (needs balancing)"
    ↓
Recommendation:
- Task 1,2 → A
- Task 3,4,5,6 → B
- Task 7,8,9,10 → A
    ↓
User confirms → PATCH /issues/ with assignees → Success
```

### Implementation Steps

#### Step 1: Create Workload Assessment
**File:** `session/session_assignment/workload_assessor.py` (NEW FILE)

```python
from typing import Dict, List
from pydantic import BaseModel

class MemberWorkload(BaseModel):
    member_id: str
    member_name: str
    current_task_count: int
    high_priority_count: int
    urgent_deadline_count: int
    skills: List[str]  # Inferred from past tasks
    capacity_score: float  # 0-1, lower = more available

class WorkloadAssessor:
    def __init__(self, plane_api):
        self.plane_api = plane_api
    
    def assess_team(self, project_id: str) -> List[MemberWorkload]:
        """Assess current workload of each team member"""
        members = self._get_members(project_id)
        workloads = []
        
        for member in members:
            tasks = self._get_member_tasks(project_id, member['id'])
            skills = self._infer_skills(tasks)
            
            workload = MemberWorkload(
                member_id=member['id'],
                member_name=member['name'],
                current_task_count=len(tasks),
                high_priority_count=len([t for t in tasks if t.get('priority') in ['high', 'urgent']]),
                urgent_deadline_count=len([t for t in tasks if self._is_urgent(t)]),
                skills=skills,
                capacity_score=self._calculate_capacity(tasks)
            )
            workloads.append(workload)
        
        return workloads
    
    def _infer_skills(self, tasks: List[Dict]) -> List[str]:
        """Infer member skills from task descriptions"""
        skills = set()
        keywords = {
            'backend': ['api', 'server', 'database'],
            'frontend': ['ui', 'component', 'page'],
            'devops': ['deploy', 'ci/cd', 'infrastructure'],
            'testing': ['test', 'qa', 'bug'],
        }
        
        for task in tasks:
            description = (task.get('description', '') + task.get('name', '')).lower()
            for skill, keywords_list in keywords.items():
                if any(kw in description for kw in keywords_list):
                    skills.add(skill)
        
        return list(skills) if skills else ['general']
```

#### Step 2: Create Assignment Strategy
**File:** `session/session_assignment/assignment_strategy.py` (NEW FILE)

```python
from typing import List, Dict
from pydantic import BaseModel

class TaskAssignment(BaseModel):
    task_id: str
    task_name: str
    assigned_to_id: str
    assigned_to_name: str
    reasoning: str

class AssignmentStrategy:
    """LLM-based assignment strategy"""
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def recommend_assignments(
        self, 
        unassigned_tasks: List[Dict],
        team_workloads: List[MemberWorkload]
    ) -> List[TaskAssignment]:
        """Use LLM to recommend task assignments"""
        
        # Format context for LLM
        context = self._format_context(unassigned_tasks, team_workloads)
        
        prompt = PROMPT_ASSIGNMENT.format(context=context)
        
        result = self.llm.generate_response(
            prompt,
            AssignmentResult  # Output schema
        )
        
        return result.assignments
    
    def _format_context(self, tasks, workloads):
        """Format tasks and workloads for LLM"""
        task_str = "\n".join([
            f"- Task {i+1}: {t['name']} (Priority: {t.get('priority', 'medium')}, Deadline: {t.get('target_date', 'N/A')})"
            for i, t in enumerate(tasks)
        ])
        
        member_str = "\n".join([
            f"- {w.member_name}: {w.current_task_count} tasks, Skills: {', '.join(w.skills)}, Capacity: {w.capacity_score:.2f}"
            for w in workloads
        ])
        
        return f"Tasks to assign:\n{task_str}\n\nTeam status:\n{member_str}"
```

#### Step 3: Create Session 4 Handler
**File:** `session/session_assignment.py` (REWRITE)

```python
from session.session_assignment.workload_assessor import WorkloadAssessor
from session.session_assignment.assignment_strategy import AssignmentStrategy
from session.session_create_project.check import AffirmativeChecker

class SessionAssignment:
    """Session 4: Intelligent Task Assignment"""
    
    def __init__(self, llm_client, api_key, workspace_slug):
        self.llm = llm_client
        self.plane_api = PlaneAPI(api_key, workspace_slug)
        self.assessor = WorkloadAssessor(self.plane_api)
        self.strategy = AssignmentStrategy(llm_client)
        self.checker = AffirmativeChecker(llm_client)
        
        self.status = None  # None, "recommended", "confirmed"
        self.pending_assignments = None
        self.project_id = None
    
    def handle_session(self, user_id, query, file_content, selected_history):
        # Extract project_id from query or context
        
        if self.status is None:
            # 1. Fetch unassigned tasks and team workload
            unassigned = self._fetch_unassigned_tasks(self.project_id)
            if not unassigned:
                return "session_assignment", "Không có task nào để giao."
            
            team_workload = self.assessor.assess_team(self.project_id)
            
            # 2. Get LLM recommendations
            assignments = self.strategy.recommend_assignments(unassigned, team_workload)
            self.pending_assignments = assignments
            self.status = "recommended"
            
            # 3. Show recommendations
            summary = self._format_assignments(assignments)
            return "session_assignment", f"Đây là gợi ý phân công:\n{summary}\n\nBạn có đồng ý không?"
        
        elif self.status == "recommended":
            # Check confirmation
            affirmative = self.checker.check(query)
            
            if str(affirmative.is_affirmative).lower() == "true":
                # Perform assignments
                success = self._perform_assignments()
                self.status = None
                self.pending_assignments = None
                
                if success:
                    return "session_assignment", "✅ Giao task thành công!"
                else:
                    return "session_assignment", "❌ Lỗi giao task. Vui lòng thử lại."
            else:
                # Cancel
                self.status = None
                self.pending_assignments = None
                return "session_assignment", "Đã hủy. Bạn cần gì khác?"
    
    def _fetch_unassigned_tasks(self, project_id):
        """Fetch tasks without assignee"""
        # GET /projects/{id}/issues/?assignees=null
        pass
    
    def _format_assignments(self, assignments):
        """Format assignments for display"""
        by_member = {}
        for assignment in assignments:
            member = assignment.assigned_to_name
            if member not in by_member:
                by_member[member] = []
            by_member[member].append(assignment.task_name)
        
        lines = []
        for member, tasks in by_member.items():
            lines.append(f"- {member}: {len(tasks)} task\n  " + ", ".join(tasks))
        return "\n".join(lines)
    
    def _perform_assignments(self):
        """Update Plane with assignments"""
        # PATCH /issues/{id}/ with {assignees: [member_id]}
        pass
```

#### Step 4: Add Prompts for Session 4
**File:** `prompt/session_assignment/prompt_assignment.py` (NEW FILE)

```python
PROMPT_ASSIGNMENT = """
Bạn là một AI chuyên về phân bổ công việc (task assignment) trong một dự án phần mềm.

Bối cảnh hiện tại:
{context}

🎯 Nhiệm vụ:
1. Phân tích:
   - Workload hiện tại của từng thành viên
   - Độ phức tạp của từng task
   - Deadline của task
   - Skills của thành viên vs yêu cầu task

2. Tìm sự cân bằng:
   - Không quá tải cho bất kỳ ai (tối đa N tasks)
   - Ưu tiên tasks với deadline sắp tới
   - Match skills nếu có thể
   - Phân phối công việc đều

3. Trả về recommendations

📤 Định dạng kết quả:
{
  "assignments": [
    {
      "task_id": "1",
      "task_name": "API Quiz",
      "assigned_to_id": "member_1",
      "assigned_to_name": "Nguyễn Văn A",
      "reasoning": "Có kinh nghiệm backend, workload thấp"
    },
    ...
  ]
}

⚠️ Lưu ý:
- Mỗi task chỉ assign cho 1 người
- Không bỏ task nào
- Giải thích rõ lý do
"""
```

### Dependencies
```bash
# No new dependencies needed
```

---

## SUMMARY TABLE: What to Implement

| Session | Handler | Extractor | API Methods | Prompts | Status |
|---------|---------|-----------|-------------|---------|--------|
| 1 | ✅ | ✅ | POST /projects/, POST /issues/ | ✅ | DONE |
| 2 | ❌ SessionQA | ❌ RAGPipeline | GET /projects/, GET /issues/, GET /members | ❌ | TODO |
| 3 | ❌ SessionUpdateInfo | ❌ UpdateExtractor | PATCH /issues/, PATCH /projects/ | ❌ | TODO |
| 4 | ❌ SessionAssignment | ❌ AssignmentStrategy | PATCH /issues/ (assignees) | ❌ | TODO |

---

## QUICK START: Minimal Implementation for Session 2

If you want to start with the simplest working version:

### 1. Install Chroma (simplest)
```bash
pip install chromadb langchain-text-splitters sentence-transformers
```

### 2. Minimal RAG Pipeline
```python
# session/rag/minimal_rag.py
from chromadb import Client

class MinimalRAG:
    def __init__(self):
        self.client = Client()
        self.collection = None
    
    def index(self, project_data):
        self.collection = self.client.create_or_get_collection("plane")
        # Simple doc creation
        docs = [
            f"{p['name']}: {p['description']}" 
            for p in project_data.get('projects', [])
        ]
        # Add to collection...
    
    def query(self, query):
        results = self.collection.query(query_texts=[query], n_results=3)
        return results
```

### 3. Simple SessionQA
```python
# session/session_qa.py
class SessionQA:
    def handle_session(self, user_id, query, file_content, selected_history):
        context = self.rag.query(query)
        prompt = f"Context: {context}\n\nQuestion: {query}"
        response = self.llm.generate_response(prompt)
        return "session_qa", response
```

This gets you 80% of the way there with minimal complexity!

---

## Testing Checklist

### Session 2 Testing
- [ ] Fetch Plane data
- [ ] Index into vector DB
- [ ] Query returns relevant docs
- [ ] LLM generates correct answer
- [ ] Error handling for empty results

### Session 3 Testing
- [ ] Extract update request
- [ ] Validate extracted fields
- [ ] Ask for missing info
- [ ] Show confirmation summary
- [ ] PATCH API call succeeds
- [ ] Handle API errors

### Session 4 Testing
- [ ] Fetch unassigned tasks
- [ ] Calculate member workload
- [ ] Get LLM recommendations
- [ ] Format assignments clearly
- [ ] Confirm before updating
- [ ] PATCH API calls succeed

