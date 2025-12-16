"""Service for extracting structured work report data."""

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

from auto_pm_agent_api.domain.prompts import PROMPT_WORK_REPORT_EXTRACT
from auto_pm_agent_api.domain.models import DailyTask, DailyTasks, WorkReportData

logger = logging.getLogger(__name__)


class WorkReportExtractor:
    """Convert free-form work reports into structured JSON using LLM."""

    def __init__(self, llm_client):
        """
        Initialize the extractor.

        Args:
            llm_client: Required LLM client used for structured extraction.
        """
        if llm_client is None:
            raise ValueError("LLM client is required for report extraction")
        self.llm = llm_client

    def extract(self, content: str) -> WorkReportData:
        """
        Extract work report data from raw content.

        Args:
            content: Raw report text provided by the user.

        Returns:
            WorkReportData with normalized fields.
        """
        if not content or not content.strip():
            raise ValueError("Nội dung không đúng yêu cầu")

        normalized_content = self._normalize_content_for_llm(content)
        prompt = PROMPT_WORK_REPORT_EXTRACT.format(report_content=normalized_content.strip())

        try:
            raw_result = self.llm.generate_response(prompt, WorkReportData)
        except Exception as exc:  # pragma: no cover - defensive guard for LLM failures
            logger.error("Failed to extract work report via LLM: %s", exc, exc_info=True)
            raise ValueError("Nội dung không đúng yêu cầu") from exc

        report = self._coerce_report(raw_result)
        report = self._normalize_report(report, original_content=content)

        if self._is_empty(report):
            raise ValueError("Nội dung không đúng yêu cầu")

        return report

    def _normalize_content_for_llm(self, content: str) -> str:
        """
        Lightly normalize inline reports to help the LLM parse structure without rule extraction.
        - Insert newlines before numbered sections and known headers.
        - Ensure bullets (+ / -) start on new lines.
        """
        text = content.strip()
        if not text:
            return text

        text = re.sub(r"\s*(\d+\.)", r"\n\1", text)
        section_pattern = r"(?i)(today work|today|work today|issues|problem|tomorrow plan|kế hoạch|plan|task|tasks|công việc)"
        text = re.sub(section_pattern + r"\s*:\s*", r"\n\1:\n", text)
        text = re.sub(r"\s*\+\s*", "\n+ ", text)
        text = re.sub(r"\s*-\s*", "\n- ", text)
        text = re.sub(r"\s*(Task\s+\d+)", r"\n\1", text, flags=re.IGNORECASE)
        return "\n".join([line.strip() for line in text.splitlines() if line.strip()])

    def _coerce_report(self, result: Any) -> WorkReportData:
        """Convert LLM output into WorkReportData."""
        if isinstance(result, WorkReportData):
            return result
        if isinstance(result, dict):
            return WorkReportData(**result)
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
                return WorkReportData(**parsed)
            except Exception:
                try:
                    return WorkReportData.model_validate_json(result)
                except Exception:
                    pass
        raise ValueError("Không thể phân tích kết quả trích xuất")

    def _normalize_report(self, report: WorkReportData, original_content: str) -> WorkReportData:
        """Trim whitespace, sanitize tasks, and backfill defaults."""
        daily = report.daily_tasks or DailyTasks()

        tasks = [self._normalize_task(task) for task in (daily.tasks or [])]
        tasks = [task for task in tasks if task.title]
        blockers = [item.strip() for item in (daily.blockers or []) if item and item.strip()]
        achievements = [
            item.strip() for item in (daily.achievements or []) if item and item.strip()
        ]

        notes = (report.notes or "").strip()
        if not notes:
            notes = self._normalize_notes(original_content)

        created_at = self._normalize_iso_timestamp(report.created_at)
        updated_at = self._normalize_iso_timestamp(report.updated_at)
        now_iso = self._current_iso()
        if not created_at:
            created_at = now_iso
        if not updated_at:
            updated_at = created_at

        normalized_daily = DailyTasks(
            tasks=tasks,
            blockers=blockers,
            achievements=achievements,
        )

        return WorkReportData(
            daily_tasks=normalized_daily,
            notes=notes,
            created_by=report.created_by,
            updated_by=report.updated_by,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _normalize_task(self, task: DailyTask) -> DailyTask:
        """Clean up a task entry and ensure required defaults."""
        title = (task.title or "").strip()
        progress = self._safe_progress(task.progress)
        status = self._normalize_status(task.status, progress)
        time_spent = self._normalize_time_spent(task.time_spent)
        task_id = self._normalize_task_id(task.id, title)

        return DailyTask(
            id=task_id,
            title=title,
            status=status,
            progress=progress,
            time_spent=time_spent,
        )

    def _normalize_notes(self, content: str) -> str:
        """Preserve the raw report in notes if LLM does not provide it."""
        text = (content or "").strip()
        if not text:
            return ""
        return f"Báo cáo công việc ngày hôm nay:\n\n{text}"

    def _normalize_status(self, status: Optional[str], progress: int) -> str:
        """Map free-form status to canonical values."""
        normalized = (status or "").strip().lower().replace(" ", "_")
        allowed = {"todo", "in_progress", "done"}
        if normalized in allowed:
            return normalized
        return self._status_from_progress(progress)

    def _safe_progress(self, progress: Optional[int]) -> int:
        """Clamp progress into a 0-100 integer range."""
        try:
            value = int(progress) if progress is not None else 0
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, value))

    def _status_from_progress(self, progress: int) -> str:
        """Infer status from progress when not provided."""
        if progress >= 100:
            return "done"
        if progress <= 0:
            return "todo"
        return "in_progress"

    def _normalize_time_spent(self, value: Optional[str]) -> Optional[str]:
        """Normalize time strings to a compact format."""
        if not value:
            return None
        text = value.strip()
        if not text:
            return None

        match = re.search(r"(\d+(?:[.,]\d+)?)", text)
        if not match:
            return text

        number = match.group(1).replace(",", ".")
        try:
            numeric_value = float(number)
        except ValueError:
            return text

        display_number = (
            str(int(numeric_value)) if numeric_value.is_integer() else f"{numeric_value}".rstrip("0").rstrip(".")
        )
        lowered = text.lower()
        if re.search(r"(phút|min)", lowered):
            return f"{display_number}m"
        return f"{display_number}h"

    def _normalize_task_id(self, task_id: Optional[str], title: str) -> Optional[str]:
        """Generate a short ID if missing."""
        if task_id and str(task_id).strip():
            return str(task_id).strip()
        if not title:
            return None

        ascii_title = unicodedata.normalize("NFKD", title)
        ascii_title = "".join(ch for ch in ascii_title if not unicodedata.combining(ch))
        words = re.findall(r"[A-Za-z0-9]+", ascii_title)
        if not words:
            return None

        code = "".join(word[0] for word in words if word)
        return code.upper()[:8] if code else None

    def _normalize_iso_timestamp(self, value: Optional[str]) -> Optional[str]:
        """Return ISO 8601 UTC timestamp or None if invalid."""
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        except ValueError:
            return None

    def _current_iso(self) -> str:
        """Current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _is_empty(self, report: WorkReportData) -> bool:
        """Check if the report contains no meaningful data."""
        daily = report.daily_tasks or DailyTasks()
        has_tasks = any(task.title for task in daily.tasks)
        has_blockers = bool(daily.blockers)
        has_achievements = bool(daily.achievements)
        has_notes = bool(report.notes and report.notes.strip())
        return not (has_tasks or has_blockers or has_achievements or has_notes)
