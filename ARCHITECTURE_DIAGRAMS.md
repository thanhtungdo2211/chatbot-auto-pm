# ARCHITECTURE DIAGRAMS & REFERENCE

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (FastAPI)                          │
│                      POST /chat {user_id, query, file}           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Agent.query()                                │
│  - File handling                                                 │
│  - Memory retrieval                                              │
│  - Session/Intent routing                                        │
│  - Response caching to Redis                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
        ▼                                 ▼
  ┌──────────────┐            ┌──────────────────────────┐
  │   Session?   │            │  Intent Classification   │
  │  (Active)    │            │  via Router.predict()    │
  │              │            │                          │
  │ Return to    │            │ - create_new_project     │
  │ existing     │            │ - update_info            │
  │ session      │            │ - ask_info               │
  └──────┬───────┘            │ - other_topics           │
         │                    └────┬────────────────────┘
         │                         │
         └──────────────┬──────────┘
                        │
         ┌──────────────┴──────────────┐
         │                             │
         ▼                             ▼
    ┌─────────────┐          ┌────────────────────┐
    │  Session 1  │          │ General Responses  │
    │  Create Proj│          │ (Non-work topics)  │
    └─────────────┘          └────────────────────┘
         │
    ┌────┴────┬─────────┬───────────┐
    │          │         │           │
    ▼          ▼         ▼           ▼
  Extract   Check    PlaneAPI   ResponseMsg
  Data      Confirm   Upload
```

## Session 1: Create Project Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                   User Uploads File                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │ SessionCreateProject.handle_session│
        │ status = None                      │
        └────────────┬───────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ PlaneExtractor.extract()       │
        │ ├─ LLM + PROMPT_PLANE_EXTRACT │
        │ └─ Return: ExtractedPlaneData  │
        └────────────┬───────────────────┘
                     │
                     ▼
        ┌────────────────────────────────┐
        │ Check is_info_project         │
        └────────────┬────────┬──────────┘
                     │        │
               FALSE │        │ TRUE
                     │        │
            ┌────────▼┐   ┌──▼────────────────────────┐
            │ Reject  │   │ status =                 │
            │ + Ask   │   │ ready_to_create_project  │
            │ again   │   │ Show extracted data      │
            └─────────┘   │ Ask confirmation         │
                          └───────────┬──────────────┘
                                      │
                                      ▼
                         ┌────────────────────────────────┐
                         │ User Confirms (next message)   │
                         └───────────┬────────────────────┘
                                     │
                                     ▼
                         ┌────────────────────────────────┐
                         │ AffirmativeChecker.check()     │
                         │ └─ LLM checks: is_affirmative  │
                         └────────┬───────────┬───────────┘
                                  │           │
                            FALSE │           │ TRUE
                                  │           │
                          ┌───────▼┐     ┌───▼─────────────────┐
                          │ Cancel │     │ PlaneAPI.upload()   │
                          │ Reset  │     │ ├─ POST /projects/  │
                          │ Status │     │ └─ POST /issues/    │
                          └────────┘     └───┬─────────────────┘
                                             │
                                             ▼
                                    ┌─────────────────────┐
                                    │ Success! Return URL │
                                    │ Reset status=None   │
                                    └─────────────────────┘
```

## Data Flow: LLM Integration

```
┌──────────────────────────────────────────────────────┐
│              LLMClient.generate_response()            │
│                                                      │
│  prompt: str + output_format: Optional[Pydantic]   │
└─────────────┬──────────────────────────────────────┘
              │
              ├─ if output_format:
              │  └─→ llm.with_structured_output(output_format)
              │      └─→ Returns: Pydantic instance
              │
              └─ else:
                 └─→ llm.invoke(prompt).content
                     └─→ Returns: str

USAGE EXAMPLES:
───────────────

1. Extract Project Data (Session 1):
   output_format = ExtractedPlaneData
   → Returns: ExtractedPlaneData(
       is_info_project=True,
       project=ProjectSchema(...),
       tasks=[TaskSchema(...), ...]
     )

2. Check Affirmative (Session 1):
   output_format = AffirmativeResult
   → Returns: AffirmativeResult(
       is_affirmative=True,
       reason="User agreed"
     )

3. Route Intent (All Sessions):
   output_format = IntentResult
   → Returns: IntentResult(
       intent="create_new_project"
     )

4. General Response (Other Topics):
   output_format = None
   → Returns: "Hello, I'm here to help..."
```

## Redis Memory Structure

```
REDIS KEY DESIGN:
─────────────────
Key: chat_history:{user_id}
Type: List (RPUSH/LRANGE)
Max Size: 10 messages (auto-trimmed)

VALUE FORMAT (JSON String):
───────────────────────────
{
  "role": "user" | "chatbot",
  "content": "actual message text"
}

EXAMPLE TIMELINE:
─────────────────
Time  │ Action                          │ Redis State
──────┼─────────────────────────────────┼──────────────────────
t1    │ User: "Hello"                   │ [{"role":"user","content":"Hello"}]
t2    │ Bot: "Hi there"                 │ [{"role":"user",...}, {"role":"chatbot",...}]
t3    │ User: "Upload file"             │ [... prev 2 ..., {"role":"user","content":"Upload..."}]
...   │ ...                             │ ...
t11   │ (10th message)                  │ [msg_1, msg_2, ..., msg_10]
t12   │ User: "New query"               │ [msg_2, msg_3, ..., msg_10, msg_11] (msg_1 trimmed)

FLOW IN Agent:
───────────────
1. Agent.get_short_memory(user_id, query)
   └─ RedisMemory.get_history(user_id)
      └─ redis.lrange(key, 0, -1)
         └─ Returns list of 10 JSON strings
      └─ Returns parsed list of dicts

2. MemorySelectBot.get_memory_select(history, query)
   └─ Filters relevant messages from history
   └─ Reduces context for next LLM call

3. Agent.save_to_memory(user_id, role, content)
   └─ RedisMemory.add_message(user_id, role, content)
      └─ redis.rpush(key, json.dumps(...))
      └─ redis.ltrim(key, -10, -1)  # Keep last 10
```

## Plane API Integration Points

```
PLANE BASE URL: {BASE_URL_PLANE}/api/v1/workspaces/{workspace_slug}

Current Implementation (Session 1):
───────────────────────────────────

1. POST /projects/
   ├─ Input: ProjectSchema {name, identifier, description}
   ├─ Payload: {name, identifier, description, network=2, is_deployed=true}
   └─ Output: Project object {id, name, ...}
      Used by: PlaneAPI.create_project()

2. POST /projects/{project_id}/issues/
   ├─ Input: TaskSchema {name, description, start_date, target_date}
   ├─ Payload: {name, description, start_date, target_date}
   └─ Output: Issue object {id, name, ...}
      Used by: PlaneAPI.create_task()

REQUIRED FOR SESSION 2 (QA with RAG):
─────────────────────────────────────
GET /projects/
├─ Return: List of all projects
└─ Used to: Index data for RAG

GET /projects/{project_id}/issues/
├─ Return: List of all tasks in project
└─ Used to: Fetch task details for context

GET /workspaces/{slug}/members/
├─ Return: List of team members
└─ Used to: Provide member info in QA

REQUIRED FOR SESSION 3 (Update Info):
─────────────────────────────────────
PATCH /issues/{issue_id}/
├─ Input: {field: new_value}
├─ Fields: name, description, start_date, target_date, priority, state
└─ Used to: Update task properties

PATCH /projects/{project_id}/
├─ Input: {field: new_value}
├─ Fields: name, description, ...
└─ Used to: Update project properties

REQUIRED FOR SESSION 4 (Assignment):
─────────────────────────────────────
PATCH /issues/{issue_id}/
├─ Input: {assignees: [member_id, ...]}
└─ Used to: Assign tasks to members

GET /workspaces/{slug}/members/
├─ Return: List with workload info
└─ Used to: Calculate per-member load

GET /issues/ (with filters)
├─ Filters: status, assignee, priority
└─ Used to: Assess current workload
```

## Intent Classification Decision Tree

```
                    ┌─ User Query
                    │
                    ▼
          ┌─────────────────────┐
          │ Router.predict()    │
          │ + Selected History  │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────────────────────┐
          │ LLM + PROPMT_ROUTER                 │
          │ (Structure output: IntentResult)    │
          └──────────┬────────────────────────┘
                     │
       ┌─────────────┼─────────────┬──────────────────┐
       │             │             │                  │
       ▼             ▼             ▼                  ▼
  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐
  │ create_  │  │ update_  │  │ ask_about_   │  │ other_   │
  │ new_     │  │ existing │  │ existing_    │  │ topics   │
  │ project  │  │ _info    │  │ info         │  │          │
  └────┬─────┘  └────┬─────┘  └──────┬───────┘  └────┬─────┘
       │             │               │               │
       │             │               │               │
       ▼             ▼               ▼               ▼
    Sess1       [TODO:Sess3]    [TODO:Sess2]    GeneralBot
    
KEY PATTERNS DETECTED:
──────────────────────
"create_new_project":
  - "tạo project", "create project", "new project"
  - Usually preceded by file upload

"update_existing_information":
  - "cập nhật", "update", "change to", "modify"
  - "rename X to Y", "set deadline to..."

"ask_about_existing_information":
  - "bao nhiêu", "how many", "status", "progress"
  - "task nào", "who is assigned"
  - [WORK-RELATED QUESTIONS ONLY]

"other_topics":
  - Anything not above
  - Non-work topics
```

## Entity Relationships in Data Models

```
┌──────────────────────────────────────────────────────┐
│                   Session 1 Data                     │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────┐
│    ExtractedPlaneData        │
├──────────────────────────────┤
│ is_info_project: bool        │
│ project: ProjectSchema       │
│ tasks: List[TaskSchema]      │
└────┬────────────────┬────────┘
     │                │
     │                └─────────────────────┐
     │                                      │
     ▼                                      ▼
┌──────────────────────┐      ┌─────────────────────────┐
│  ProjectSchema       │      │  TaskSchema (x Many)    │
├──────────────────────┤      ├─────────────────────────┤
│ name: str            │      │ name: str               │
│ identifier: str      │      │ description: Optional   │
│ description: Opt     │      │ start_date: Opt (YYYY-) │
└──────────────────────┘      │ target_date: Opt        │
                              └─────────────────────────┘

PLANE API MAPPING:
──────────────────
ProjectSchema ──POST──→ /projects/
                        ├─ Returns: project_id

TaskSchema ────POST──→ /projects/{project_id}/issues/
                       └─ Uses: project_id from above
```

## Session State Machine

```
╔════════════════════════════════════════════════════════╗
║              SessionCreateProject States               ║
╚════════════════════════════════════════════════════════╝

          ┌─────────────────────┐
          │   Initial State     │
          │   status = None     │
          └──────────┬──────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    [No File]              [File Provided]
         │                       │
         ▼                       ▼
    ┌────────┐        ┌──────────────────────┐
    │ Reject │        │ Extract Project Data │
    │ + Ask  │        │ PlaneExtractor       │
    └────────┘        │ status = ?           │
                      └──────────┬───────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                        │
              [Invalid]                [Valid]
                    │                        │
                    ▼                        ▼
            ┌──────────────┐    ┌────────────────────────┐
            │ Reject Again │    │ Ready to Confirm       │
            │              │    │ status = ready_to_     │
            └──────────────┘    │ create_project         │
                                │                        │
                                │ Show extracted data    │
                                │ Ask user confirmation  │
                                └───────────┬────────────┘
                                            │
                              ┌─────────────┴──────────────┐
                              │                           │
                         [Confirmed]              [Rejected]
                              │                           │
                              ▼                           ▼
                    ┌──────────────────┐      ┌─────────────────┐
                    │ Upload to Plane  │      │ Cancel & Reset  │
                    │ PlaneAPI.upload()│      │ status = None   │
                    │                  │      │                 │
                    │ POST /projects/  │      │ Ready for new   │
                    │ POST /issues/    │      │ request         │
                    └────────┬─────────┘      └─────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
               [Success]         [Error]
                    │                 │
                    ▼                 ▼
            ┌──────────────┐  ┌──────────────┐
            │ Success Msg  │  │ Error Msg    │
            │ + Reset      │  │ + Reset?     │
            │ status=None  │  │              │
            └──────────────┘  └──────────────┘
```

## Error Handling Flow

```
┌────────────────────────────────────────┐
│        Exception Handling in Flow       │
└────────────────────────────────────────┘

Agent.query()
  ├─ try:
  │   ├─ File check → file_content validation
  │   ├─ Memory retrieval → Redis error handling
  │   ├─ Router.predict() → LLM error
  │   ├─ SessionCreateProject.handle_session()
  │   │   ├─ PlaneExtractor.extract() → JSON parsing
  │   │   ├─ AffirmativeChecker.check() → JSON parsing
  │   │   └─ PlaneAPI methods
  │   │       ├─ HTTP 201/200 → Success
  │   │       ├─ HTTP 4xx/5xx → Log error + return response
  │   │       └─ Network error → return error message
  │   │
  │   └─ Save to memory → Redis error handling
  │
  └─ catch:
     └─ Return: "Xin lỗi, tôi không thể xử lý yêu cầu..."

CURRENT STATE:
──────────────
✓ PlaneAPI: Basic error logging (prints to console)
✓ AffirmativeChecker: Returns structured output (safe)
✓ PlaneExtractor: Returns structured output (safe)
✗ Agent.query(): No try-except block
✗ Router: No error handling for LLM failures
✗ Memory: Fallback to API if Redis empty
```

