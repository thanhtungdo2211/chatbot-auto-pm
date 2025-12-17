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
                return (
                    True,
                    "Đã ghi nhận nội dung báo cáo và cập nhật bản nháp. Bạn có thể tiếp tục bổ sung hoặc nói 'kết thúc báo cáo' để gửi.",
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
                return (
                    True,
                    "Đã ghi nhận nội dung đánh giá/báo cáo và cập nhật bản nháp. Bạn có thể tiếp tục bổ sung hoặc nói 'kết thúc báo cáo' để đóng.",
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
            task_lines.append(
                f"- {issue.get('name')} | project: {t.get('project_name')} | trạng thái: {issue.get('state')} | start: {issue.get('start_date')} | target: {issue.get('target_date')}"
            )
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
                    lines.append(
                        f"  • {iss.get('issue_name')} | assignees: {assignees_text} | báo cáo: {'có' if has_report else 'chưa có'}"
                    )
        prompt = (
            "Bạn là manager assistant. Hãy tóm tắt các task và tình trạng báo cáo của ngày nói trên.\n"
            "Yêu cầu bản tóm tắt nêu rõ: task nào đã có báo cáo (nếu có thì ngắn gọn nội dung), task nào chưa có báo cáo. "
            "Mời manager đặt câu hỏi hoặc bổ sung đánh giá. Tránh chỉ ghi phần trăm, hãy nhấn mạnh kết quả cụ thể/đầu ra và vướng mắc.\n"
            + "\n".join(lines)
        )
        try:
            resp = self.general_bot.generate_response(history_str, prompt)
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

        mgr_list = []
        for mgr in payload.get("manager", []):
            q = mgr.get("query") or {}
            projects = q.get("projects") or []
            new_projects = []
            for p in projects:
                issues = p.get("issues") or []
                new_issues = []
                for iss in issues:
                    assignees = resolve_ids(iss.get("assignee_ids"))
                    new_issues.append({**iss, "assignee_details": assignees})
                new_projects.append({**p, "issues": new_issues})
            mgr_list.append({**mgr, "query": {**q, "projects": new_projects}})

        return {
            "manager": mgr_list,
            "manager_summary_day": payload.get("manager_summary_day"),
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

        try:
            issues = plane_api.list_issues(assignee=str(plane_user_id))
        except Exception as exc:
            self.logger.warning("Không lấy được danh sách issues để cập nhật báo cáo: %s", exc)
            return "Không thể đẩy báo cáo lên Plane (lỗi lấy danh sách task)."

        if not issues:
            return "Không tìm thấy task nào của bạn để cập nhật báo cáo."

        updated_count = 0
        failed = 0
        today_str = date.today().isoformat()
        for issue in issues:
            try:
                project_id = getattr(issue, "project", None)
                issue_id = getattr(issue, "id", None)
                if not project_id or not issue_id:
                    continue

                payload = {
                    "day": today_str,
                    "notes": report_text,
                    "daily_tasks": {
                        "tasks": [
                            {
                                "title": getattr(issue, "name", ""),
                                "status": getattr(issue, "state", "") or "in_progress",
                                "progress": None,
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

