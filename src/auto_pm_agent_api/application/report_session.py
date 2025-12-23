"""
Report session manager: handle report creation/review flows for staff and manager.
Encapsulates report state, LLM rewriting, and Plane push.
"""

import logging
from datetime import date
from typing import Callable, Optional, Tuple, List


class ReportSessionManager:
    """Manage per-user report sessions, including LLM rewrite and Plane sync."""

    def __init__(self, general_bot, plane_factory=None):
        self.sessions = {}
        self.general_bot = general_bot
        self.plane_factory = plane_factory
        self.logger = logging.getLogger(__name__)

    # ---------- Public API ----------
    def handle_staff(
        self,
        user_id: int,
        role: str,
        query: Optional[str],
        history_str: str,
        mode_report_flag: bool,
        qa_fallback: Callable[[], str],
        extra_staff_payload: Optional[dict] = None,
    ) -> Tuple[bool, str, bool]:
        """
        Handle staff report logic. Returns (handled, response, mode_report).
        Staff has only QA + report flows; router is skipped when mode_report=False.
        """
        state = self._get_state(user_id, role)
        self._activate_if_flag(
            state,
            mode_report_flag,
            query,
            user_id,
            extra_manager_payload=None,
            extra_staff_payload=extra_staff_payload,
        )

        if state["mode_report"]:
            # First response when entering report mode
            if not state.get("first_prompt_sent"):
                state["first_prompt_sent"] = True
                self.sessions[user_id] = state
                return True, self._build_staff_first_response(state, user_id, history_str), True

            if self._is_report_finish(query):
                summary = self._summarize_report(state)
                pushed_msg = self._push_report_to_plane(user_id, state)
                response = f"{summary}\n{pushed_msg}"
                self.sessions[user_id] = self._empty_state(role)
                return True, response, False

            if self._is_report_statement(query):
                updated_text = self._update_report_with_llm(state, query, history_str)
                state.setdefault("infor_report", []).append(query or "")
                state["report_text"] = updated_text
                state["status"] = "collecting"
                state["mode_report"] = True
                self.sessions[user_id] = state
                # Provide feedback with brief summary
                feedback = self._generate_acknowledgment_feedback(query, "staff")
                return (
                    True,
                    feedback + "\n\nBạn có thể tiếp tục bổ sung hoặc nói 'kết thúc báo cáo' để gửi.",
                    True,
                )

            if self._is_report_info_request(query):
                return True, self._summarize_report(state), True

            # Other queries while in report mode: allow QA on own tasks but keep mode_report
            qa_response = qa_fallback()
            return True, qa_response, True

        # mode_report=False → only QA for staff
        qa_response = qa_fallback()
        return True, qa_response, False

    def handle_manager(
        self,
        user_id: int,
        role: str,
        query: Optional[str],
        history_str: str,
        mode_report_flag: bool,
        extra_manager_payload: Optional[dict] = None,
    ) -> Tuple[bool, Optional[str], bool]:
        """
        Handle manager report/review logic. Returns (handled, response, mode_report).
        If not handled, caller continues normal router/flows and keeps mode_report flag as is.
        """
        state = self._get_state(user_id, role)
        self._activate_if_flag(
            state,
            mode_report_flag,
            query,
            user_id,
            extra_manager_payload=extra_manager_payload,
            extra_staff_payload=None,
        )

        if state["mode_report"]:
            # First response when entering report mode (manager view)
            if not state.get("first_prompt_sent"):
                state["first_prompt_sent"] = True
                self.sessions[user_id] = state
                return True, self._build_manager_first_response(state, user_id, history_str), True

            if self._is_report_finish(query):
                summary = self._summarize_report(state)
                pushed_msg = self._push_report_to_plane(user_id, state)
                response = f"{summary}\n{pushed_msg}"
                self.sessions[user_id] = self._empty_state(role)
                return True, response, False

            if self._is_report_review_statement(query) or self._is_report_statement(query):
                updated_text = self._update_report_with_llm(state, query, history_str)
                state.setdefault("infor_report", []).append(query or "")
                state["report_text"] = updated_text
                state["status"] = "reviewing"
                state["mode_report"] = True
                self.sessions[user_id] = state
                # Provide feedback with brief summary
                feedback = self._generate_acknowledgment_feedback(query, "manager")
                return (
                    True,
                    feedback + "\n\nBạn có thể tiếp tục bổ sung đánh giá hoặc nói 'kết thúc đánh giá báo cáo' để đóng.",
                    True,
                )

            if self._is_report_info_request(query):
                return True, self._summarize_report(state), True

        # Not handled; keep current mode_report state
        self.sessions[user_id] = state
        return False, None, state.get("mode_report", False)

    # ---------- Internal helpers ----------
    def _get_state(self, user_id: int, role: str) -> dict:
        return self.sessions.get(user_id, self._empty_state(role))

    def _empty_state(self, role: str) -> dict:
        return {
            "mode_report": False,
            "infor_report": [],
            "report_text": "",
            "status": None,
            "role": role,
        }

    def _activate_if_flag(
        self,
        state: dict,
        mode_flag: bool,
        query: Optional[str],
        user_id: int,
        extra_manager_payload: Optional[dict],
        extra_staff_payload: Optional[dict],
    ) -> None:
        if mode_flag and not state.get("mode_report"):
            # Log the input that triggered report-mode activation for manager
            if (state.get("role") or "").lower() == "manager":
                try:
                    import json

                    def _trunc(value: object, limit: int) -> str:
                        text = str(value) if value is not None else ""
                        return text if len(text) <= limit else text[:limit] + "...(truncated)"

                    payload_preview = ""
                    if extra_manager_payload is not None:
                        try:
                            payload_preview = json.dumps(
                                extra_manager_payload, ensure_ascii=False, sort_keys=True
                            )
                        except Exception:
                            payload_preview = str(extra_manager_payload)

                    self.logger.info(
                        "Report mode activated (manager): user_id=%s day=%s query=%s extra_manager_payload=%s",
                        user_id,
                        state.get("day") or date.today().isoformat(),
                        _trunc(query, 800),
                        _trunc(payload_preview, 2000),
                    )
                except Exception:
                    # Never block activation on logging issues
                    pass

            if query:
                state["infor_report"] = [query]
                report_text = (state.get("report_text") or "").strip()
                state["report_text"] = f"{report_text}\n{query}".strip() if report_text else query
            state["status"] = "collecting"
            state["mode_report"] = True
            # Seed report context từ Plane
            if self.plane_factory:
                try:
                    plane_api = self.plane_factory.get_api(user_id)
                    # Nếu có payload staff thì ưu tiên dùng payload; nếu không thì lấy từ Plane
                    state["report_context"] = (
                        self._build_report_context_from_staff_payload(extra_staff_payload)
                        if extra_staff_payload
                        else self._build_report_context(plane_api, extra_manager_payload)
                    )
                except Exception as exc:
                    self.logger.warning("Không lấy được report context từ Plane: %s", exc)
                    state["report_context"] = self._build_report_context_from_staff_payload(extra_staff_payload)
            else:
                # Nếu không có plane_factory, vẫn giữ payload manager nếu có
                state["report_context"] = self._build_manager_payload_only(extra_manager_payload)

    def _is_report_statement(self, query: Optional[str]) -> bool:
        if not query:
            return False
        q = query.lower()
        keywords = [
            "báo cáo",
            "report",
            "hôm nay",
            "tiến độ",
            "công việc hôm nay",
            "summary",
            "daily",
            "cập nhật báo cáo",
            "update report",
            "nhật ký làm việc",
            "log công việc",
        ]
        return any(k in q for k in keywords)

    def _is_report_finish(self, query: Optional[str]) -> bool:
        if not query:
            return False
        q = query.lower()
        finish_kw = [
            "kết thúc báo cáo",
            "kết thúc đánh giá",
            "kết thúc đánh giá báo cáo",
            "xong báo cáo",
            "xong đánh giá",
            "kết thúc report",
            "finish report",
            "done report",
            "gửi báo cáo",
            "đóng báo cáo",
            "đóng đánh giá",
        ]
        return any(k in q for k in finish_kw)

    def _is_report_info_request(self, query: Optional[str]) -> bool:
        if not query:
            return False
        q = query.lower()
        kw = ["tóm tắt báo cáo", "xem báo cáo", "infor_report", "nội dung báo cáo", "báo cáo hiện tại"]
        return any(k in q for k in kw)

    def _is_report_review_statement(self, query: Optional[str]) -> bool:
        if not query:
            return False
        q = query.lower()
        review_kw = ["đánh giá báo cáo", "review báo cáo", "feedback báo cáo", "nhận xét báo cáo", "duyệt báo cáo"]
        return any(k in q for k in review_kw)

    def _generate_acknowledgment_feedback(self, query: Optional[str], role: str) -> str:
        """
        Generate a brief acknowledgment with key points from the query.
        Extract important keywords to show we understood the content.
        """
        if not query or len(query.strip()) < 10:
            return "Đã ghi nhận nội dung."

        # Extract key phrases/info
        q = query.strip()
        feedback_parts = []

        if role == "manager":
            feedback_parts.append("Đã ghi nhận đánh giá của bạn")
        else:
            feedback_parts.append("Đã ghi nhận báo cáo của bạn")

        # Extract task mentions
        import re
        task_pattern = r'(?:task|module|công việc|dự án)\s+([A-Za-z0-9\s]+?)(?:\s+|:|,|;|\.)'
        task_matches = re.findall(task_pattern, q.lower(), re.IGNORECASE)
        if task_matches:
            tasks = [m.strip().title() for m in task_matches[:2]]  # Limit to 2
            feedback_parts.append(f"về {', '.join(tasks)}")

        # Extract completion/status indicators
        completion_keywords = {
            "hoàn thành": "đã hoàn thành",
            "xong": "đã xong",
            "chưa có": "chưa có tiến độ",
            "đang làm": "đang thực hiện",
            "blocker": "có vướng mắc",
            "vướng mắc": "có vướng mắc",
            "cần hỗ trợ": "cần hỗ trợ",
        }
        statuses = []
        for kw, status in completion_keywords.items():
            if kw in q.lower():
                statuses.append(status)
                if len(statuses) >= 2:
                    break

        if statuses:
            feedback_parts.append(f"({', '.join(statuses)})")

        # Build final message
        if len(feedback_parts) > 1:
            return ". ".join(feedback_parts) + "."
        return "Đã ghi nhận nội dung và cập nhật bản nháp."

    def _summarize_report(self, state: dict) -> str:
        report_text = (state.get("report_text") or "").strip()
        if report_text:
            return f"Nội dung báo cáo hiện tại:\n{report_text}"
        info_list: List[str] = state.get("infor_report") or []
        if not info_list:
            return "Chưa có nội dung báo cáo nào được lưu."
        numbered = "\n".join([f"- {item}" for item in info_list if item])
        return f"Nội dung báo cáo đã lưu:\n{numbered}"

    # ---------- First response builders ----------
    def _build_staff_first_response(self, state: dict, user_id: int, history_str: str) -> str:
        ctx = state.get("report_context") or {}
        staff_list = ctx.get("staff") or []
        uid_str = str(user_id)
        entry = None
        for s in staff_list:
            if str(s.get("user_id")) == uid_str:
                entry = s
                break
        if not entry and staff_list:
            entry = staff_list[0]
        tasks = entry.get("tasks", []) if entry else []
        task_lines = []
        for t in tasks:
            issue = t.get("issue") or {}
            # Build task info without raw state ID
            task_info_parts = [
                f"- **{issue.get('name')}**",
                f"Dự án: {t.get('project_name')}",
            ]
            if issue.get('start_date'):
                task_info_parts.append(f"Bắt đầu: {issue.get('start_date')}")
            if issue.get('target_date'):
                task_info_parts.append(f"Deadline: {issue.get('target_date')}")
            if issue.get('priority') and issue.get('priority') != 'none':
                task_info_parts.append(f"Độ ưu tiên: {issue.get('priority')}")

            task_lines.append(" | ".join(task_info_parts))
        tasks_text = "\n".join(task_lines) if task_lines else "Chưa có task nào được giao."
        tasks_brief = "Các task bạn cần báo cáo:\n" + (tasks_text if task_lines else "Không có task.")
        prompt = (
            "Bạn là trợ lý PM. Đây là phiên báo cáo hằng ngày.\n"
            "Hãy yêu cầu nhân viên báo cáo NGẮN GỌN nhưng CỤ THỂ theo 3 mục:\n"
            "1) Tiến độ hôm nay: ghi rõ đã làm gì, đầu ra cụ thể (tài liệu, code, chức năng), trạng thái từng task; tránh chỉ ghi phần trăm.\n"
            "2) Vướng mắc/blockers: mô tả chi tiết đang kẹt ở đâu, cần hỗ trợ gì.\n"
            "3) Kế hoạch tiếp theo/ngày mai: bước kế tiếp cụ thể.\n"
            f"{tasks_brief}\n"
            "Nhấn mạnh yêu cầu nêu rõ kết quả/đầu ra và vướng mắc, không chỉ nêu phần trăm."
        )
        try:
            resp = self.general_bot.generate_response(history_str, prompt)
            self._log_llm(channel="staff_first", user_id=user_id, role="staff", prompt=prompt, response=resp)
            return resp
        except Exception as exc:
            self.logger.warning("LLM first response staff failed: %s", exc)
            return (
                "Bắt đầu phiên báo cáo. Vui lòng báo cáo: (1) Tiến độ hôm nay (đầu ra cụ thể, không chỉ %), "
                "(2) Vướng mắc đang gặp (chi tiết), (3) Kế hoạch tiếp theo. "
                f"Tasks của bạn:\n{tasks_text}"
            )

    def _build_manager_first_response(self, state: dict, user_id: int, history_str: str) -> str:
        ctx = state.get("report_context") or {}
        mgrs = ctx.get("manager") or []
        entry = mgrs[0] if mgrs else {}
        q = entry.get("query") or {}
        day = q.get("day") or ctx.get("manager_summary_day") or "chưa xác định"
        projects = q.get("projects") or []
        lines = [f"Ngày báo cáo: {day}"]
        if not projects:
            lines.append("Chưa có báo cáo nào cho ngày này.")
        else:
            for p in projects:
                lines.append(f"- Dự án: {p.get('project_name')} (id: {p.get('project_id')})")
                issues = p.get("issues") or []
                for iss in issues:
                    assignees = iss.get("assignee_details") or iss.get("assignee_ids") or []
                    if isinstance(assignees, list):
                        assignees_text = ", ".join(
                            [a.get("resolved") if isinstance(a, dict) else str(a) for a in assignees]
                        )
                    else:
                        assignees_text = str(assignees)
                    has_report = iss.get("has_report")
                    progress_entries = iss.get("progress_entries") or []

                    # Build detailed line with progress info if available
                    if has_report and progress_entries:
                        # Extract full info from progress entries
                        progress_details = []
                        for entry in progress_entries[:3]:  # Show up to 3 most recent entries
                            detail_parts = []

                            # Extract daily_tasks info
                            daily_tasks = entry.get("daily_tasks", {})
                            tasks = daily_tasks.get("tasks", [])
                            if tasks:
                                task_summaries = []
                                for task in tasks:
                                    task_info = f"{task.get('title', 'N/A')}: {task.get('status', 'unknown')}"
                                    if task.get('progress') is not None:
                                        task_info += f" ({task.get('progress')}%)"
                                    if task.get('time_spent'):
                                        task_info += f", time: {task.get('time_spent')}"
                                    task_summaries.append(task_info)
                                detail_parts.append("Tasks: " + "; ".join(task_summaries))

                            # Extract blockers
                            blockers = daily_tasks.get("blockers", [])
                            if blockers:
                                detail_parts.append(f"Blockers: {', '.join(blockers)}")

                            # Extract achievements
                            achievements = daily_tasks.get("achievements", [])
                            if achievements:
                                detail_parts.append(f"Achievements: {', '.join(achievements)}")

                            # Add notes (full text, not truncated)
                            notes = entry.get("notes", "")
                            if notes:
                                detail_parts.append(f"Notes: {notes}")

                            # Add day if available
                            day = entry.get("day", "")
                            if day:
                                detail_parts.insert(0, f"Day: {day}")

                            if detail_parts:
                                progress_details.append(" | ".join(detail_parts))

                        progress_text = "\n      ".join(progress_details) if progress_details else "có báo cáo nhưng chưa có chi tiết"
                        lines.append(
                            f"  • {iss.get('issue_name')} | assignees: {assignees_text} | báo cáo: có\n      {progress_text}"
                        )
                    else:
                        lines.append(
                            f"  • {iss.get('issue_name')} | assignees: {assignees_text} | báo cáo: chưa có"
                        )
        prompt = (
            "Bạn là manager assistant. Hãy tóm tắt các task và tình trạng báo cáo của ngày nói trên (nói rõ tình trạng về nội dung, ...).\n"
            "QUAN TRỌNG: CHỈ sử dụng thông tin có trong dữ liệu bên dưới. KHÔNG tự thêm hoặc suy đoán thông tin.\n"
            "- Với task đã có báo cáo: tóm tắt ngắn gọn nội dung đã cung cấp\n"
            "- Với task chưa có báo cáo: nêu rõ là chưa có\n"
            "Mời manager đặt câu hỏi hoặc bổ sung đánh giá. Nhấn mạnh kết quả cụ thể/đầu ra và vướng mắc, tránh chỉ ghi phần trăm. \n\n"
            "Nếu chưa có báo cáo cho task nào vẫn phải liệt kê các task ra với tình trạng là chưa có báo cáo. "
            "Dữ liệu:\n" + "\n".join(lines)
        )
        try:
            # Don't use history for first response to avoid hallucination from old data
            resp = self.general_bot.generate_response("", prompt)
            self._log_llm(channel="manager_first", user_id=user_id, role="manager", prompt=prompt, response=resp)
            return resp
        except Exception as exc:
            self.logger.warning("LLM first response manager failed: %s", exc)
            return "\n".join(lines + ["(Bạn có thể đặt câu hỏi hoặc yêu cầu đánh giá thêm)"])

    def _update_report_with_llm(self, state: dict, query: Optional[str], history_str: str) -> str:
        """
        Use LLM (general_bot) to rewrite/update the current report draft based on the new query.
        Falls back to simple append if LLM fails.
        """
        current_text = (state.get("report_text") or "").strip()
        update_request = query or ""
        prompt = (
            "Bạn là trợ lý PM. Hãy cập nhật bản báo cáo ngắn gọn, rõ ràng, ưu tiên tính CỤ THỂ:\n"
            "- Tiến độ: nêu rõ đã làm gì, đầu ra/artefact (code, tài liệu, chức năng), trạng thái từng task; tránh chỉ nêu phần trăm.\n"
            "- Vướng mắc: mô tả chi tiết đang kẹt gì, cần hỗ trợ gì.\n"
            "- Kế hoạch tiếp theo: bước kế tiếp rõ ràng.\n"
            "Giữ lại nội dung cũ nếu chưa bị thay thế, bổ sung phần mới nếu cần.\n"
            "Báo cáo hiện tại:\n"
            f"{current_text or '(chưa có)'}\n\n"
            "Yêu cầu cập nhật:\n"
            f"{update_request}\n\n"
            "Trả về toàn bộ báo cáo sau khi chỉnh sửa."
        )
        try:
            updated = self.general_bot.generate_response(history_str, prompt)
            self._log_llm(channel="update_report", user_id=None, role=state.get("role"), prompt=prompt, response=updated)
            return (updated or "").strip()
        except Exception as exc:
            self.logger.warning("LLM update report failed, fallback append: %s", exc)
            merged = current_text
            if merged:
                merged += "\n"
            merged += update_request
            return merged.strip()

    # ---------- Context builder ----------
    def _build_report_context(self, plane_api, extra_manager_payload: Optional[dict] = None) -> dict:
        """
        Build structured context for report session:
        - staff: tasks grouped by assignee (id -> display_name, email, role)
        - manager: nếu có payload từ client (day, projects, issues, progress_entries)
        """
        context = {
            "staff": [],
            "manager": [],
            "manager_summary_day": None,
            "task_job_chatbot": False,
        }

        # Fetch workspace members map
        member_map = {}
        try:
            members = plane_api.list_members()
            for m in members:
                mid = getattr(m, "id", None) or m.get("id")
                if not mid:
                    continue
                display = getattr(m, "display_name", None) or getattr(m, "email", None) or m.get("display_name") or m.get("email") or mid
                email = getattr(m, "email", None) or m.get("email")
                role = getattr(m, "role", None) or m.get("role")
                member_map[mid] = {"id": mid, "display_name": display, "email": email, "role": role}
        except Exception as exc:
            self.logger.warning("Không lấy được members: %s", exc)

        # Group tasks by assignee
        staff_map = {}
        try:
            projects = plane_api.list_projects()
        except Exception as exc:
            self.logger.warning("Không lấy được projects: %s", exc)
            projects = []

        for p in projects:
            pid = getattr(p, "id", None) or p.get("id")
            pname = getattr(p, "name", None) or p.get("name")
            issues = []
            try:
                issues = plane_api.list_issues(project_id=pid)
            except Exception as exc:
                self.logger.warning("Không lấy được issues cho project %s: %s", pname, exc)
            for iss in issues:
                # Normalize assignees (list or single)
                raw_assignees = getattr(iss, "assignees", None) or getattr(iss, "assignee", None) or []
                if isinstance(raw_assignees, str):
                    raw_assignees = [raw_assignees]
                if not raw_assignees:
                    continue
                issue_data = {
                    "id": getattr(iss, "id", None) or iss.get("id"),
                    "name": getattr(iss, "name", None) or iss.get("name"),
                    "priority": getattr(iss, "priority", None) or iss.get("priority"),
                    "start_date": getattr(iss, "start_date", None) or iss.get("start_date"),
                    "target_date": getattr(iss, "target_date", None) or iss.get("target_date"),
                    "state": getattr(iss, "state", None) or iss.get("state"),
                    "description_html": getattr(iss, "description_html", None) or iss.get("description_html"),
                }
                for aid in raw_assignees:
                    mem = member_map.get(aid) or {"id": aid, "display_name": aid, "email": None, "role": None}
                    entry = staff_map.setdefault(
                        aid,
                        {
                            "user_id": aid,
                            "role": "staff",
                            "display_name": mem.get("display_name"),
                            "email": mem.get("email"),
                            "task_count": 0,
                            "tasks": [],
                        },
                    )
                    entry["tasks"].append(
                        {
                            "project_name": pname,
                            "project_id": pid,
                            "issue": issue_data,
                        }
                    )

        # Finalize staff list
        for aid, info in staff_map.items():
            tasks = info.get("tasks", [])
            info["task_count"] = len(tasks)
            info["task_names_preview"] = ", ".join([t["issue"].get("name") for t in tasks[:3] if t.get("issue")])
            context["staff"].append(info)

        # Manager block: nạp từ payload nếu có
        manager_payload = self._build_manager_payload_only(extra_manager_payload, member_map)
        if manager_payload:
            context["manager"] = manager_payload.get("manager", [])
            context["manager_summary_day"] = manager_payload.get("manager_summary_day")
            context["task_job_chatbot"] = manager_payload.get("task_job_chatbot", False)
        return context

    def _build_manager_payload_only(self, payload: Optional[dict], member_map: Optional[dict] = None) -> dict:
        """
        Nhận payload manager dạng:
        {
          "manager": [{ "user_id":..., "role":"manager", "query":{day, projects:[{project_id, project_name, issues:[{issue_id, issue_name, assignee_ids, has_report, progress_entries}]}], total_projects, total_issues}, "file_content":"", "mode_report":true }],
          "manager_summary_day": "2025-12-16",
          "task_job_chatbot": false
        }
        Resolve assignee_ids -> display/email/role nếu có member_map.

        Ngoài ra chấp nhận payload dạng "query trực tiếp" (không bọc key `manager`):
        {
          "day": "2025-12-16",
          "projects": [...],
          "total_projects": 2,
          "total_issues": 10,
          "task_job_chatbot": false
        }
        """
        if not payload:
            return {}

        def resolve_ids(ids):
            if not ids:
                return []
            if isinstance(ids, str):
                ids = [ids]
            res = []
            for aid in ids:
                mem = (member_map or {}).get(aid) or {}
                disp = mem.get("display_name") or mem.get("email") or aid
                email = mem.get("email")
                role = mem.get("role")
                extra = []
                if email:
                    extra.append(email)
                if role is not None:
                    extra.append(f"role={role}")
                res.append({"id": aid, "display_name": disp, "email": email, "role": role, "resolved": ", ".join([disp] + extra) if extra else disp})
            return res

        # Normalize payload: accept either wrapped payload["manager"] or direct query payload
        mgr_items = payload.get("manager")
        if not mgr_items and any(k in payload for k in ("day", "projects", "total_projects", "total_issues")):
            mgr_items = [
                {
                    "user_id": payload.get("user_id"),
                    "role": "manager",
                    "query": {
                        "day": payload.get("day") or payload.get("manager_summary_day"),
                        "projects": payload.get("projects") or [],
                        "total_projects": payload.get("total_projects"),
                        "total_issues": payload.get("total_issues"),
                    },
                    "mode_report": True,
                }
            ]
        if not isinstance(mgr_items, list):
            mgr_items = []

        mgr_list = []
        for mgr in mgr_items:
            q = mgr.get("query") or {}
            projects = q.get("projects") or []
            new_projects = []
            for p in projects:
                # Accept a few common variants: {name,id} or {project_name,project_id}
                project_name = p.get("project_name") or p.get("name")
                project_id = p.get("project_id") or p.get("id")
                issues = p.get("issues") or []
                new_issues = []
                for iss in issues:
                    # Accept variants: {name,id} or {issue_name,issue_id}
                    issue_name = iss.get("issue_name") or iss.get("name")
                    issue_id = iss.get("issue_id") or iss.get("id")
                    assignees = resolve_ids(iss.get("assignee_ids"))
                    new_issues.append(
                        {
                            **iss,
                            "issue_name": issue_name,
                            "issue_id": issue_id,
                            "assignee_details": assignees,
                        }
                    )
                new_projects.append(
                    {
                        **p,
                        "project_name": project_name,
                        "project_id": project_id,
                        "issues": new_issues,
                    }
                )
            mgr_list.append({**mgr, "query": {**q, "projects": new_projects}})

        return {
            "manager": mgr_list,
            "manager_summary_day": payload.get("manager_summary_day") or payload.get("day"),
            "task_job_chatbot": payload.get("task_job_chatbot", False),
        }

    def _build_report_context_from_staff_payload(self, payload: Optional[dict]) -> dict:
        """
        Xây dựng report_context từ payload staff (JSON đã parse).
        Payload dạng:
        {
          "user_id": "...",
          "role": "staff",
          "display_name": "...",
          "task_count": n,
          "tasks": [{project_name, project_id, issue:{...}}, ...],
          "task_names_preview": "..."
        }
        """
        if not payload:
            return {"staff": [], "manager": [], "manager_summary_day": None, "task_job_chatbot": False}
        return {
            "staff": [payload],
            "manager": [],
            "manager_summary_day": None,
            "task_job_chatbot": False,
        }

    # ---------- Logging helper ----------
    def _log_llm(self, channel: str, user_id: Optional[int], role: Optional[str], prompt: str, response: str) -> None:
        """Append LLM prompt/response to a jsonl log file."""
        import json
        import os
        record = {
            "channel": channel,
            "user_id": user_id,
            "role": role,
            "prompt": prompt,
            "response": response,
        }
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/report_llm_logs.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            self.logger.warning("Không ghi được log LLM: %s", exc)

    def _push_report_to_plane(self, user_id: int, state: dict) -> str:
        """
        Ghi daily progress lên Plane thay vì cập nhật description trực tiếp.
        - Tìm issues gán cho user (map Zalo -> Plane nếu có).
        - Với mỗi issue, cố gắng tạo daily-progress cho ngày hiện tại; nếu đã có thì patch.
        """
        if not self.plane_factory:
            return "Không thể đẩy lên Plane vì thiếu cấu hình Plane API."

        report_text = (state.get("report_text") or "").strip()
        if not report_text:
            return "Không có nội dung báo cáo để đẩy lên Plane."

        try:
            plane_api = self.plane_factory.get_api(user_id)
        except Exception as exc:
            self.logger.warning("Không khởi tạo được Plane API: %s", exc)
            return "Không thể đẩy báo cáo lên Plane (khởi tạo API lỗi)."

        # Map Zalo user -> Plane user id nếu có
        plane_user_id = str(user_id)
        try:
            user_obj = plane_api.get_user_by_zalo_id(str(user_id))
            plane_user_id = user_obj.get("id") or plane_user_id
        except Exception as exc:
            self.logger.warning("Không map được Zalo id sang Plane id, dùng user_id thô: %s", exc)

        today_str = date.today().isoformat()
        issues = self._get_report_target_issues(
            plane_api=plane_api,
            state=state,
            plane_user_id=str(plane_user_id),
            today_str=today_str,
        )

        if not issues:
            return "Không tìm thấy task nào của bạn để cập nhật báo cáo."

        updated_count = 0
        failed = 0
        for issue in issues:
            try:
                # issue can be a PlaneIssue object or a normalized dict (from report_context)
                if isinstance(issue, dict):
                    project_id = issue.get("project_id")
                    issue_id = issue.get("issue_id")
                    issue_name = issue.get("issue_name") or ""
                else:
                    project_id = getattr(issue, "project", None)
                    issue_id = getattr(issue, "id", None)
                    issue_name = getattr(issue, "name", "") or ""
                if not project_id or not issue_id:
                    continue

                payload = {
                    "day": today_str,
                    "notes": report_text,
                    "daily_tasks": {
                        "tasks": [
                            {
                                "id": str(issue_id),
                                "title": issue_name,
                                # Use a safe, API-docs-aligned status value
                                "status": "in_progress",
                                "progress": 0,
                                "time_spent": None,
                            }
                        ],
                        "blockers": [],
                        "achievements": [],
                    },
                }

                # Thử tạo mới; nếu đã tồn tại, fallback patch entry đầu tiên trong ngày
                try:
                    plane_api.create_daily_progress(project_id=project_id, issue_id=issue_id, payload=payload)
                    updated_count += 1
                    continue
                except Exception as exc_create:
                    self.logger.info("Tạo daily progress thất bại, thử patch: %s", exc_create)
                    try:
                        existing = plane_api.list_daily_progress(project_id, issue_id, day=today_str)
                        if existing:
                            prog_id = existing[0].get("id") if isinstance(existing[0], dict) else getattr(existing[0], "id", None)
                            if prog_id:
                                plane_api.update_daily_progress(project_id, issue_id, prog_id, payload)
                                updated_count += 1
                                continue
                    except Exception as exc_patch:
                        self.logger.warning(
                            "Patch daily progress thất bại issue %s: %s", issue_id, exc_patch
                        )
                failed += 1
            except Exception as exc:
                failed += 1
                self.logger.warning(
                    "Không cập nhật được issue %s: %s", getattr(issue, "id", "?"), exc
                )
                continue

        if updated_count == 0:
            return "Không thể cập nhật daily progress nào với báo cáo."
        if failed > 0:
            return f"Đã cập nhật daily progress cho {updated_count} task; {failed} task lỗi."
        return f"Đã cập nhật daily progress cho {updated_count} task trên Plane."

    def _get_report_target_issues(
        self,
        plane_api,
        state: dict,
        plane_user_id: str,
        today_str: str,
    ) -> list:
        """
        Chọn danh sách issues cần update report theo đúng cách trong `api-docs`:
        - Ưu tiên dùng `state['report_context']` (đã build từ list_projects + list_issues(project_id))
        - Fallback: list_projects + list_issues(project_id) rồi tự lọc theo assignees và (nếu có) start/target date.
        """
        # 1) Prefer report_context (staff payload / prebuilt context)
        ctx = state.get("report_context") or {}
        staff_entries = ctx.get("staff") or []
        for entry in staff_entries:
            if str(entry.get("user_id")) != str(plane_user_id):
                continue
            tasks = entry.get("tasks") or []
            results = []
            for t in tasks:
                issue = t.get("issue") or {}
                pid = t.get("project_id")
                iid = issue.get("id")
                if pid and iid:
                    results.append(
                        {
                            "project_id": pid,
                            "issue_id": iid,
                            "issue_name": issue.get("name"),
                            "start_date": issue.get("start_date"),
                            "target_date": issue.get("target_date"),
                        }
                    )
            if results:
                return results

        # 2) Fallback: fetch using "api-docs" approach (no `assignee` filter in request)
        try:
            projects = plane_api.list_projects()
        except Exception as exc:
            self.logger.warning("Không lấy được projects để lọc task báo cáo: %s", exc)
            return []

        matched = []
        for project in projects or []:
            pid = getattr(project, "id", None) or (project.get("id") if isinstance(project, dict) else None)
            if not pid:
                continue
            try:
                issues = plane_api.list_issues(project_id=pid)
            except Exception as exc:
                pname = getattr(project, "name", None) or (project.get("name") if isinstance(project, dict) else pid)
                self.logger.warning("Không lấy được issues cho project %s: %s", pname, exc)
                continue

            for iss in issues or []:
                # Normalize assignees (list or single)
                raw_assignees = getattr(iss, "assignees", None) or getattr(iss, "assignee", None) or []
                if isinstance(raw_assignees, str):
                    raw_assignees = [raw_assignees]
                if not raw_assignees or str(plane_user_id) not in [str(x) for x in raw_assignees]:
                    continue

                # Filter to "today tasks" if both dates are present (as in api-docs/query_task_today.py)
                start_date = getattr(iss, "start_date", None)
                target_date = getattr(iss, "target_date", None)
                if start_date and target_date:
                    try:
                        if not (str(start_date) <= today_str <= str(target_date)):
                            continue
                    except Exception:
                        # If comparison fails, don't filter out
                        pass

                matched.append(iss)

        return matched
