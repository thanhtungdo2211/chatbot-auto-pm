# AI PM CHATBOT - COMPLETE DOCUMENTATION INDEX

This document serves as an index to all generated documentation about the codebase.

## Generated Documentation Files

### 1. CODEBASE_ANALYSIS.md
**What:** Deep dive into the entire codebase structure
**Contains:**
- Project overview and tech stack
- Complete directory structure with file descriptions
- Environment configuration
- Data models and schemas
- Architecture and data flows
- LLM integration details
- Prompt engineering for each component
- Memory management system
- Utility bots and routers
- Plane API integration
- Session manager architecture
- Key findings and gaps
- Security issues
- Code quality notes
- Dependencies list

**Read this if:** You want to understand every part of the codebase in detail

**Length:** ~3000 lines

---

### 2. ARCHITECTURE_DIAGRAMS.md
**What:** Visual representations of system architecture and flows
**Contains:**
- System architecture diagram
- Session 1 complete workflow
- LLM integration data flow
- Redis memory structure
- Plane API integration points
- Intent classification decision tree
- Entity relationships in data models
- Session state machine
- Error handling flow

**Read this if:** You're a visual learner or need to present to others

**Length:** ASCII diagrams, ~600 lines

---

### 3. IMPLEMENTATION_GUIDE.md
**What:** Step-by-step guide to implement Sessions 2, 3, and 4
**Contains:**
- Session 1 recap (what's already done)
- Session 2 (QA with RAG) - detailed implementation steps
  - Vector DB choices (Qdrant vs Chroma)
  - Embedding model selection
  - RAG pipeline creation
  - Plane data fetching
  - Session handler code
  - Prompts
- Session 3 (Update Info) - detailed implementation steps
  - Update extractor design
  - Plane API update methods needed
  - Session handler with state machine
  - Prompts
- Session 4 (Task Assignment) - detailed implementation steps
  - Workload assessment
  - Assignment strategy
  - Session handler
  - Prompts
- Testing checklist for each session
- Quick start for minimal implementation

**Read this if:** You're implementing Sessions 2, 3, or 4

**Length:** ~800 lines of structured pseudocode

---

### 4. QUICK_START.md
**What:** Fast overview and implementation patterns
**Contains:**
- 5-minute overview of all 4 sessions
- Key files to understand first
- How Session 1 works (detailed flow)
- Implementation outlines for Sessions 2, 3, 4
- Common patterns to reuse
- Testing examples for each session
- Environment setup
- Important notes
- Next steps

**Read this if:** You just want to get up to speed quickly

**Length:** ~400 lines, organized for quick reading

---

### 5. README.md (Original)
**What:** Project requirements in Vietnamese
**Contains:**
- Session specifications from user perspective
- Dialog examples
- Logic and processing steps
- Summary table

**Read this if:** You need to understand the requirements/user stories

---

## How to Use These Documents

### For First-Time Reading
1. Start with **QUICK_START.md** (5 mins)
2. Then **CODEBASE_ANALYSIS.md** sections:
   - Overall Project Structure (2-3 mins)
   - Key Files to Understand (2-3 mins)
   - Session 1 Implementation (5 mins)
3. Check **ARCHITECTURE_DIAGRAMS.md** for visuals (10 mins)

**Total time: 20-30 minutes to understand the project**

### For Session 2 Implementation
1. **QUICK_START.md** - Session 2 section (5 mins)
2. **IMPLEMENTATION_GUIDE.md** - Session 2 section (30 mins)
3. **CODEBASE_ANALYSIS.md** - RAG & Plane API sections (10 mins)
4. **ARCHITECTURE_DIAGRAMS.md** - System architecture (10 mins)

### For Session 3 Implementation
1. **QUICK_START.md** - Session 3 section (5 mins)
2. **IMPLEMENTATION_GUIDE.md** - Session 3 section (20 mins)
3. Study **Session 1 implementation** (use as pattern reference)
4. **CODEBASE_ANALYSIS.md** - Plane API section (10 mins)

### For Session 4 Implementation
1. **QUICK_START.md** - Session 4 section (5 mins)
2. **IMPLEMENTATION_GUIDE.md** - Session 4 section (25 mins)
3. Study **Session 1 implementation** (use as pattern reference)
4. **CODEBASE_ANALYSIS.md** - Plane API section (10 mins)

---

## Key Concepts Summary

### Architecture Pattern
This is a **Multi-Session State Machine Chatbot**:
- User makes request → Router classifies intent → Session handler takes over
- Session uses state machine (self.status) to handle multi-turn conversations
- Each session can be a complex workflow with confirmations and validations

### Data Flow
```
API Request
  ↓
Agent.query() - Orchestrator
  ├─ Get Redis memory (last 10 messages)
  ├─ Route by intent or active session
  ├─ Call appropriate handler
  ├─ Save response to Redis
  └─ Return response
```

### Session Pattern (Reusable)
```python
class SessionX:
    status = None  # Track multi-turn state
    
    def handle_session(self, user_id, query, file_content, history):
        if self.status is None:
            # Extract/validate input
            if error:
                return None, "Ask user for clarification"
            self.status = "next_state"
            return "session_x", "Here's what I found. Confirm?"
        
        elif self.status == "next_state":
            # Check confirmation or get more input
            self.status = None  # Reset
            # Execute action (API call, etc.)
            return None, "Success!"
```

### LLM Usage Pattern
```python
# For structured outputs (JSON)
result = llm.generate_response(prompt, OutputSchema)
# Returns: OutputSchema instance (validated)

# For text responses
text = llm.generate_response(prompt)
# Returns: str
```

### Plane API Pattern
```python
# Create
POST /projects/                      → Creates project
POST /projects/{id}/issues/          → Creates task

# Read
GET /projects/                       → List projects [TODO]
GET /projects/{id}/issues/           → List tasks [TODO]
GET /workspaces/{slug}/members/      → List members [TODO]

# Update
PATCH /projects/{id}/                → Update project [TODO]
PATCH /issues/{id}/                  → Update task [TODO]
```

---

## File Organization Reference

```
/Chatbotnew/
├── QUICK_START.md              ← START HERE
├── CODEBASE_ANALYSIS.md        ← Deep dive
├── ARCHITECTURE_DIAGRAMS.md    ← Visual reference
├── IMPLEMENTATION_GUIDE.md     ← How to build Sessions 2-4
├── INDEX.md                    ← This file
├── readme.md                   ← Original requirements
│
├── api.py                      ← FastAPI entry point
├── agent.py                    ← Main orchestrator
│
├── llm/
│   └── llm_client.py           ← LLM wrapper
│
├── memory/
│   └── redis_memory.py         ← Conversation storage
│
├── utils/
│   ├── router.py               ← Intent classifier
│   ├── memory_select_bot.py    ← History filter
│   └── genaral_bot.py          ← General responses
│
├── prompt/
│   ├── utils/                  ← Shared prompts
│   └── session_create_project/ ← Session 1 prompts
│
└── session/
    ├── session_manager.py              ← Routes sessions
    ├── session_create_project/         ← Session 1 (COMPLETE)
    │   ├── session_create_project.py
    │   ├── plane_extractor.py
    │   ├── check.py
    │   ├── update_plane.py
    │   └── prompt/
    ├── session_qa.py                   ← Session 2 (TODO)
    ├── session_update_info.py          ← Session 3 (TODO)
    └── session_assignment.py           ← Session 4 (TODO)
```

---

## Status Summary

| Component | Status | Priority | Est. Effort |
|-----------|--------|----------|------------|
| Session 1 - Create Project | COMPLETE | - | - |
| Session 2 - QA with RAG | NOT STARTED | HIGH | 2-3 days |
| Session 3 - Update Info | SKELETON | HIGH | 1-2 days |
| Session 4 - Task Assignment | SKELETON | HIGH | 1-2 days |
| Security fixes | NEEDED | HIGH | 1 day |
| Error handling | NEEDED | MEDIUM | 1 day |
| Code cleanup | OPTIONAL | LOW | 1 day |

---

## Quick Questions & Answers

**Q: How do I add a new session?**
A: Follow the pattern in Session 1:
1. Create `session/session_mynewsession.py` with state machine
2. Add handler to `session_manager.py`
3. Add prompts to `prompt/session_mynewsession/`
4. Add route in `agent.py` if needed

**Q: How do I change the LLM provider?**
A: Modify `llm/llm_client.py` - currently uses OpenRouter, can switch to direct Gemini/OpenAI

**Q: How do I add new Plane API endpoints?**
A: Add methods to `PlaneAPI` class in `session/session_create_project/update_plane.py`

**Q: How do I fix the hardcoded credentials?**
A: Move to `.env`:
- API keys → API_KEY, GOOGLE_API_KEY
- Plane credentials → Pass as parameters

**Q: How do I deploy this?**
A: Currently single-instance MVP. For production:
1. Use distributed session storage (not Redis in-memory)
2. Add proper authentication
3. Use API keys from secrets manager
4. Add error handling throughout
5. Load test

---

## Notes for Developers

1. **Session State is Per-Session**: Each session instance has its own state. For multi-user, you may need per-user session instances.

2. **Redis Memory is Global**: All users share last 10 messages. Consider per-user memory in production.

3. **LLM Costs**: Uses Google Gemini via OpenRouter. Monitor API calls and costs.

4. **Plane API Authentication**: Uses hardcoded key in code - move to .env immediately!

5. **Vector DB Choice**: Session 2 hasn't chosen between Qdrant/Chroma yet - see IMPLEMENTATION_GUIDE for comparison.

6. **Vietnamese-First**: Most prompts and comments are in Vietnamese. Keep for consistency.

7. **Error Handling**: Minimal in current code - add try-except in Agent.query() and all API calls.

---

## Contributing Guidelines

When implementing new sessions:
1. Follow Session 1 pattern for state machine
2. Use Pydantic for LLM structured outputs
3. Add prompts to `prompt/` directory
4. Update SessionManager routing
5. Test with QUICK_START.md examples
6. Update this INDEX.md if structure changes

---

Generated: November 18, 2025
Total Documentation: 4 comprehensive files + original README
Total Lines: ~5000+ lines of analysis and implementation guidance
