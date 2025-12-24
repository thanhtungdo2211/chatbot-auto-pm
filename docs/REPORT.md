Report: Chatbot role/report logic overview and test plan
========================================================

Scope
-----
- Review current logic for staff/manager flows, report session handling, LLM rewrite, and Plane push integration.
- No automated tests were executed in this run (analysis only).

Key behaviors (code paths)
--------------------------
- API models: `ChatRequest` includes `user_id`, `role`, `mode_report`; `ChatResponse` returns `mode_report`.
- ChatService:
  - Staff:
    - If `mode_report=false`: skip router, QA only on tasks assigned to `user_id` (assignee filter); fallback general bot if no data.
    - If `mode_report=true`: report_session_manager handles start/collect/finish; LLM rewrites report text; “kết thúc báo cáo” pushes to Plane, then mode_report→False; can ask to summarize current report.
  - Manager:
    - If `mode_report=false`: original router (QA/assignment/update/create/general).
    - If `mode_report=true`: report_session_manager handles review/collect/finish; keeps other active sessions intact; LLM rewrites; “kết thúc báo cáo” pushes to Plane, then mode_report→False; can ask to summarize report; other intents still go through normal flow when not consumed by report logic.
- ReportSessionManager (new file):
  - State per user: `mode_report`, `infor_report`, `report_text`, `status`, `role`.
  - Detects start when mode_report flag switches false→true; seeds first query into report_text/infor_report.
  - Recognizes: report statements, review statements (manager), finish, summarize.
  - Uses `general_bot` to rewrite report text (`_update_report_with_llm`), fallback append.
  - Pushes report_text to Plane: append to description of issues with `assignee=str(user_id)`; best-effort, returns message.
- QA service: supports `assignee_filter`; staff QA calls with assignee=user_id.

Potential gaps / risks
----------------------
- Assignee mapping: uses `assignee=str(user_id)`; if Plane assignee ID/email differs, report push/QA filter may miss tasks.
- Plane push appends raw report_text; no HTML formatting; repeated pushes will keep appending.
- Report keyword detection is heuristic; false positives/negatives possible.
- Active sessions: manager report flow is non-intrusive but relies on current code path ordering; ensure report handling is called before intent router (currently yes).
- Memory: history limited to last 5 messages; may truncate long report context for LLM rewrite.

Suggested manual test plan (not executed)
-----------------------------------------
- Staff, QA only:
  - Input: role=staff, mode_report=false, query about own task → expect QA answer filtered to assignee.
  - Unrelated query → fallback general bot.
- Staff, start report:
  - Send query with mode_report=true (report statement) → report_text saved, response acknowledges.
  - Add more report statements → report_text rewritten (LLM) and kept.
  - Ask “tóm tắt báo cáo” → returns current report_text.
  - Say “kết thúc báo cáo” → pushes to Plane descriptions, mode_report=false.
- Manager, normal flows:
  - mode_report=false, create/update/assignment/QA still work (router path).
- Manager, review report:
  - Flip mode_report=true with first statement → saved in report_text.
  - Add review statement → report_text rewritten and stored.
  - Ask “tóm tắt báo cáo” → returns report_text.
  - Say “kết thúc báo cáo” → pushes to Plane, mode_report=false, other active sessions unaffected.
- Plane push:
  - Ensure Plane config present; verify descriptions of assignee tasks updated with report_text; check idempotency/duplicate appends.

Notes for further improvement
-----------------------------
- Add explicit assignee mapping (user_id → Plane member id/email) to avoid mismatches.
- Add throttling/dedup for Plane description updates to reduce duplicates.
- Expand keyword sets or use LLM classification for report/review detection.

