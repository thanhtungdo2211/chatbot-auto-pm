"""QA service implementation with hybrid RAG retrieval for project Q&A."""

import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field

from auto_pm_agent_api.domain.prompts import PROMPT_QA_RAG

logger = logging.getLogger(__name__)


class QAResponse(BaseModel):
    """Structured response schema for QA answers."""

    answer: str = Field(..., description="Câu trả lời cho câu hỏi của người dùng")
    found_data: bool = Field(..., description="True nếu tìm thấy dữ liệu liên quan")
    related_items: Optional[List[str]] = Field(
        None, description="Danh sách các items liên quan"
    )


class HybridRAGRetriever:
    """
    Hybrid RAG: dense embeddings (OpenAI) + lexical TF-IDF for better recall/precision.
    Defaults to OpenAI embeddings for quality; falls back to local TF-IDF if unavailable.
    """

    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        backend: Optional[str] = None,
        dense_weight: float = 0.65,
        sparse_weight: float = 0.35,
        type_boost: Optional[Dict[str, float]] = None,
    ):
        self.embedding_model = embedding_model
        self.backend = (
            backend or os.getenv("RAG_EMBEDDING_BACKEND") or "openai"
        ).lower()
        self.init_error: Optional[str] = None
        self.use_openai = False
        self._init_backend()
        self.documents: List[Dict[str, Any]] = []
        self.dense_vectors: Optional[np.ndarray] = None
        self.sparse_vectors: Optional[np.ndarray] = None
        self.vocab: Dict[str, int] = {}
        self.idf: Optional[np.ndarray] = None
        self.data_signature: Optional[int] = None
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.type_boost = type_boost or {"issue": 1.15, "project": 1.0, "member": 0.9}

    def _init_backend(self) -> None:
        """Choose embedding backend. Preferred: OpenAI; fallback: local TF-IDF only."""
        if self.backend == "openai":
            try:
                self.embeddings = OpenAIEmbeddings(
                    model=self.embedding_model,
                    api_key=os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY"),
                    base_url=os.getenv("BASE_URL"),
                )
                self.use_openai = True
                return
            except Exception as exc:  # pragma: no cover - defensive guard
                self.init_error = f"OpenAIEmbeddings fallback to local: {exc}"
                self.backend = "local"

        self.embeddings = None
        self.use_openai = False

    def build_signature(self, data: List[Dict[str, Any]]) -> int:
        """Create a quick signature to know when to rebuild the index."""
        try:
            return hash(json.dumps(data, sort_keys=True, ensure_ascii=False))
        except TypeError:
            return len(data)

    def _item_to_document(self, item: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Convert a Plane record into a text chunk for embedding."""
        item_type = item.get("type")

        if item_type == "project":
            name = item.get("name") or "Không rõ tên dự án"
            desc = item.get("description") or "Không có mô tả"
            text = f"Dự án {name}. Mô tả: {desc}."
            meta = {"type": "project", "name": name}
            return text, meta

        if item_type == "issue":
            name = item.get("name") or "Task không tên"
            project = item.get("project_name") or "dự án không xác định"
            desc = item.get("description") or "Không có mô tả"
            priority = item.get("priority") or "none"
            start = item.get("start_date") or "không rõ"
            target = item.get("target_date") or "không rõ"
            state = item.get("state_name") or "không rõ trạng thái"
            assignees = item.get("assignees") or []
            assignee_text = (
                f"{len(assignees)} người phụ trách"
                if assignees
                else "Chưa giao người phụ trách"
            )
            text = (
                f"Task {name} thuộc dự án {project}. "
                f"Trạng thái {state}. Ưu tiên {priority}. "
                f"Thời gian: {start} -> {target}. "
                f"{assignee_text}. Mô tả: {desc}"
            )
            meta = {"type": "issue", "name": name, "project_name": project, "state": state}
            return text, meta

        if item_type == "member":
            name = item.get("name") or "Thành viên không tên"
            email = item.get("email") or "không rõ email"
            role = item.get("role") or "không rõ vai trò"
            project = item.get("project_name") or "workspace"
            text = f"Thành viên {name} trong {project}. Email: {email}. Vai trò: {role}."
            meta = {"type": "member", "name": name, "project_name": project}
            return text, meta

        return None, None

    def index_data(self, data: List[Dict[str, Any]], signature: Optional[int] = None) -> None:
        """Embed and index Plane data for later retrieval."""
        docs = []
        for item in data:
            text, meta = self._item_to_document(item)
            if text:
                docs.append({"text": text, "meta": meta})

        if not docs:
            self.documents = []
            self.dense_vectors = None
            self.sparse_vectors = None
            self.vocab = {}
            self.idf = None
            self.data_signature = signature
            return

        texts = [d["text"] for d in docs]
        self.sparse_vectors = self._embed_texts_sparse(texts)
        self.dense_vectors = self._embed_texts_dense(texts)

        self.documents = docs
        self.data_signature = signature

    def ensure_index(self, data: List[Dict[str, Any]], signature: int) -> None:
        """Rebuild index only when data changes."""
        if (
            (self.dense_vectors is None and self.sparse_vectors is None)
            or signature != self.data_signature
        ):
            self.index_data(data, signature)

    def search(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """Return top-k relevant chunks for the query."""
        if not self.documents:
            return []

        dense_scores = None
        sparse_scores = None

        if self.dense_vectors is not None and self.use_openai:
            q_dense = np.array(self._embed_query_dense(query), dtype=float)
            dense_scores = self._cosine_scores(q_dense, self.dense_vectors)

        if self.sparse_vectors is not None:
            q_sparse = np.array(self._embed_query_sparse(query), dtype=float)
            sparse_scores = self._cosine_scores(q_sparse, self.sparse_vectors)

        combined = []
        for idx in range(len(self.documents)):
            score_dense = dense_scores[idx] if dense_scores is not None else 0.0
            score_sparse = sparse_scores[idx] if sparse_scores is not None else 0.0
            score = self.dense_weight * score_dense + self.sparse_weight * score_sparse
            score = max(score, 0.0)
            boost = self.type_boost.get(self.documents[idx]["meta"].get("type"), 1.0)
            score *= boost
            combined.append((score, idx))

        combined.sort(key=lambda x: x[0], reverse=True)
        top_indices = [idx for score, idx in combined[:top_k] if score > 0]
        if not top_indices:
            return []

        results: List[Dict[str, Any]] = []
        for score, idx in [(s, i) for s, i in combined[:top_k] if s > 0]:
            results.append(
                {
                    "text": self.documents[idx]["text"],
                    "meta": self.documents[idx]["meta"],
                    "score": float(score),
                }
            )
        return results

    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """Human-readable context for the prompt."""
        if not results:
            return "Không có dữ liệu liên quan"

        lines: List[str] = []
        for i, item in enumerate(results, 1):
            meta = item.get("meta", {}) or {}
            label = meta.get("type", "data").upper()
            name = meta.get("name") or meta.get("project_name") or ""
            score = item.get("score", 0)
            state = meta.get("state")
            header = f"{i}. [{label}] {name}".strip()
            if state and label == "ISSUE":
                header += f" | Trạng thái: {state}"
            lines.append(header)
            lines.append(f"   {item.get('text', '').strip()} (score={score:.3f})")

        return "\n".join(lines)

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def _fit_vocab(self, texts: List[str]) -> None:
        vocab_set = set()
        doc_freq: Dict[str, int] = {}
        for text in texts:
            tokens = self._tokenize(text)
            unique_tokens = set(tokens)
            vocab_set.update(tokens)
            for tok in unique_tokens:
                doc_freq[tok] = doc_freq.get(tok, 0) + 1

        self.vocab = {tok: idx for idx, tok in enumerate(sorted(vocab_set))}
        total_docs = max(len(texts), 1)
        self.idf = np.array(
            [math.log((total_docs + 1) / (doc_freq.get(tok, 0) + 1)) + 1 for tok in self.vocab],
            dtype=float,
        )

    def _embed_texts_sparse(self, texts: List[str]) -> np.ndarray:
        if not self.vocab or self.idf is None:
            self._fit_vocab(texts)

        vectors = np.zeros((len(texts), len(self.vocab)), dtype=float)
        for i, text in enumerate(texts):
            tokens = self._tokenize(text)
            for tok in tokens:
                if tok in self.vocab:
                    vectors[i, self.vocab[tok]] += 1.0

        vectors *= self.idf
        norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-10
        return vectors / norms

    def _embed_texts_dense(self, texts: List[str]) -> Optional[np.ndarray]:
        if not self.use_openai:
            return None
        try:
            vectors = np.array(self.embeddings.embed_documents(texts), dtype=float)
            norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-10
            return vectors / norms
        except Exception as exc:  # pragma: no cover - depends on env
            self.init_error = f"Dense embedding failed, using sparse only: {exc}"
            self.use_openai = False
            return None

    def _embed_query_dense(self, query: str) -> Optional[np.ndarray]:
        if not self.use_openai:
            return None
        vec = np.array(self.embeddings.embed_query(query), dtype=float)
        norm = np.linalg.norm(vec) + 1e-10
        return vec / norm

    def _embed_query_sparse(self, query: str) -> np.ndarray:
        if not self.vocab or self.idf is None:
            self._fit_vocab([query])
        vec = np.zeros((len(self.vocab)), dtype=float)
        for tok in self._tokenize(query):
            if tok in self.vocab:
                vec[self.vocab[tok]] += 1.0
        vec *= self.idf
        norm = np.linalg.norm(vec) + 1e-10
        return vec / norm

    def _cosine_scores(self, query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        return matrix @ query_vec


class GraphStructuredRetriever:
    """
    Build simple project→issues→members graph to return structured context.
    Uses HybridRAGRetriever scores and groups by project when possible.
    """

    def __init__(self, base_retriever: HybridRAGRetriever):
        self.base = base_retriever
        self.signature: Optional[int] = None
        self.graph: Dict[str, Dict[str, Any]] = {}

    def rebuild_graph(self, data: List[Dict[str, Any]], signature: int) -> None:
        if signature == self.signature:
            return

        graph: Dict[str, Dict[str, Any]] = {}

        for item in data:
            if item.get("type") == "project":
                name = item.get("name") or ""
                key = name.lower()
                graph[key] = {
                    "name": name,
                    "description": item.get("description") or "",
                    "issues": [],
                    "members": [],
                }

        for item in data:
            if item.get("type") == "issue":
                project = (item.get("project_name") or "").lower()
                if not project:
                    continue
                if project not in graph:
                    graph[project] = {
                        "name": item.get("project_name") or "",
                        "description": "",
                        "issues": [],
                        "members": [],
                    }
                graph[project]["issues"].append(item)

        for item in data:
            if item.get("type") == "member":
                project = (item.get("project_name") or "").lower()
                # Bỏ qua members ở mức workspace để không tạo project ảo "workspace"
                if not project or project == "workspace":
                    continue
                if project not in graph:
                    graph[project] = {
                        "name": item.get("project_name") or "",
                        "description": "",
                        "issues": [],
                        "members": [],
                    }
                graph[project]["members"].append(item)

        self.graph = graph
        self.signature = signature

    def _detect_projects(self, query: str) -> List[str]:
        q = query.lower()
        matches = []
        for key in self.graph:
            if key and key in q:
                matches.append(key)
        return matches

    def _format_project_block(
        self,
        project_key: str,
        base_results: List[Dict[str, Any]],
        max_issues: int = 6,
        max_members: int = 4,
    ) -> List[str]:
        info = self.graph.get(project_key) or {}
        name = info.get("name") or project_key
        desc = info.get("description") or "Không có mô tả"

        lines = [f"=== DỰ ÁN: {name} ===", f"Mô tả: {desc}"]

        retrieved_issue_names = [
            (item.get("meta") or {}).get("name", "").lower()
            for item in base_results
            if (item.get("meta") or {}).get("project_name", "").lower() == project_key
            and (item.get("meta") or {}).get("type") == "issue"
        ]

        issues = info.get("issues", [])
        ordered: List[Dict[str, Any]] = []
        seen = set()
        for issue in issues:
            iname = (issue.get("name") or "").lower()
            if iname in retrieved_issue_names and iname not in seen:
                ordered.append(issue)
                seen.add(iname)
        for issue in issues:
            iname = (issue.get("name") or "").lower()
            if iname not in seen:
                ordered.append(issue)
                seen.add(iname)

        if ordered:
            lines.append("Tasks:")
            for issue in ordered[:max_issues]:
                name_issue = issue.get("name") or "Task không tên"
                priority = issue.get("priority") or "none"
                state_raw = issue.get("state_name") or issue.get("state") or ""
                state_label = self._normalize_state(state_raw)
                completion = "chưa hoàn thành" if state_label != "done" else "đã hoàn thành"
                start = issue.get("start_date") or "không rõ"
                target = issue.get("target_date") or "không rõ"
                assignees = issue.get("assignees") or []
                lines.append(
                    f"- {name_issue} | Trạng thái: {state_label} ({completion}), "
                    f"Ưu tiên: {priority}, Thời gian: {start}->{target}, "
                    f"Assignees: {len(assignees)}"
                )

        members = info.get("members", [])
        if members:
            lines.append("Thành viên:")
            for member in members[:max_members]:
                lines.append(
                    f"- {member.get('name')} | Email: {member.get('email')} | "
                    f"Vai trò: {member.get('role')}"
                )

        return lines

    def _normalize_state(self, state: str) -> str:
        if not state:
            return "không rõ"
        low = state.lower()
        done_keywords = ["done", "hoàn thành", "closed", "resolved"]
        for kw in done_keywords:
            if kw in low:
                return "done"
        return state

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", (text or "").lower())

    def _rerank(self, query: str, results: List[Dict[str, Any]], final_k: int) -> List[Dict[str, Any]]:
        """Lightweight reranker: combine base score with keyword overlap."""
        if not results:
            return results

        q_tokens = set(self._tokenize(query))
        reranked = []
        for item in results:
            text = item.get("text", "")
            base_score = float(item.get("score", 0))
            doc_tokens = set(self._tokenize(text))
            overlap = len(q_tokens & doc_tokens)
            overlap_score = overlap / max(len(q_tokens), 1)
            final_score = 0.7 * base_score + 0.3 * overlap_score
            reranked.append({**item, "score": final_score})

        reranked.sort(key=lambda x: x.get("score", 0), reverse=True)
        return reranked[:final_k]

    def retrieve_context(self, query: str, top_k: int = 10) -> str:
        base_results = self.base.search(query, top_k=top_k * 3)
        base_results = self._rerank(query, base_results, final_k=top_k)
        if not base_results and not self.graph:
            return "Không có dữ liệu liên quan"

        lines: List[str] = []
        project_names = [v.get("name") for v in self.graph.values() if v.get("name")]
        if project_names:
            lines.append(f"=== TỔNG QUAN DỰ ÁN ({len(project_names)}) ===")
            for name in project_names:
                lines.append(f"- {name}")
            lines.append("")

        project_matches = self._detect_projects(query)
        target_projects = project_matches if project_matches else sorted(self.graph.keys())

        used_projects = set()
        for key in target_projects:
            if key in used_projects or key is None:
                continue
            used_projects.add(key)
            lines.extend(
                self._format_project_block(
                    key, base_results, max_issues=top_k, max_members=4
                )
            )
            lines.append("")

        if not lines:
            return self.base.format_results(base_results)

        return "\n".join(lines).strip()


class QAService:
    """
    Service for answering questions about projects, tasks, and members using RAG.
    """

    def __init__(self, llm_client, plane_api_factory):
        self.llm = llm_client
        self.plane_api_factory = plane_api_factory
        self.rag = HybridRAGRetriever()
        self.structured_rag = GraphStructuredRetriever(self.rag)

    def handle_query(self, user_id: int, query: str, assignee_filter: Optional[str] = None) -> Tuple[Optional[str], str]:
        """
        Handle a QA query about projects/tasks.

        Returns:
            Tuple of (session_state, response_message)
        """
        try:
            plane_api = self.plane_api_factory.get_api(user_id)
            data = self._fetch_rag_data(plane_api, assignee_filter=assignee_filter)

            if not data:
                return None, (
                    "Không tìm thấy dữ liệu dự án nào. "
                    "Vui lòng kiểm tra kết nối với Plane API."
                )

            data_signature = self.rag.build_signature(data)
            try:
                self.rag.ensure_index(data, data_signature)
                self.structured_rag.rebuild_graph(data, data_signature)
            except Exception as exc:
                logger.error("Failed to build RAG index", exc_info=True)
                return None, f"Lỗi khi xây dựng bộ nhớ RAG: {exc}"

            context = self.structured_rag.retrieve_context(query, top_k=10)
            if not context:
                return None, "Không tìm thấy dữ liệu liên quan để trả lời."

            prompt = PROMPT_QA_RAG.format(
                context=context,
                query=query,
                history="Không có lịch sử",
            )
            response = self.llm.generate_response(prompt)
            return None, response
        except Exception as exc:  # pragma: no cover - runtime integration
            logger.error(f"Error in QA service: {exc}", exc_info=True)
            return None, f"Đã xảy ra lỗi khi xử lý câu hỏi: {str(exc)}"

    def _fetch_rag_data(self, plane_api, assignee_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch and normalize project data for RAG.
        """
        data: List[Dict[str, Any]] = []
        project_lookup: Dict[str, str] = {}
        member_map: Dict[str, Dict[str, Any]] = {}

        try:
            projects = plane_api.list_projects()
        except Exception as exc:
            logger.error(f"Error fetching projects: {exc}", exc_info=True)
            return data

        for project in projects:
            project_name = getattr(project, "name", "") or "Không rõ tên dự án"
            project_data = {
                "type": "project",
                "name": project_name,
                "identifier": getattr(project, "identifier", None),
                "description": getattr(project, "description", None) or "Không có mô tả",
                "workspace": getattr(project, "workspace", None),
            }
            data.append(project_data)
            project_lookup[getattr(project, "id", project_name)] = project_name

        for project in projects:
            project_name = getattr(project, "name", "") or "Không rõ tên dự án"
            try:
                issues = plane_api.list_issues(
                    project_id=getattr(project, "id"),
                    assignee=assignee_filter if assignee_filter else None,
                )
            except Exception as exc:
                logger.warning(
                    "Could not fetch issues for project %s: %s", project_name, exc
                )
                continue

            for issue in issues:
                if assignee_filter:
                    raw_assignees = getattr(issue, "assignees", None) or getattr(issue, "assignee", None) or []
                    if isinstance(raw_assignees, str):
                        raw_assignees = [raw_assignees]
                    if assignee_filter not in raw_assignees:
                        continue
                data.append(self._normalize_issue(issue, project_name, member_map))

            members = self._safe_list_members(plane_api, getattr(project, "id"), project_name)
            # cập nhật map để resolve assignees
            for mem in members:
                mid = mem.get("id")
                if mid:
                    member_map[mid] = mem
            data.extend(members)

        workspace_members = self._safe_workspace_members(plane_api)
        if workspace_members:
            for mem in workspace_members:
                mid = mem.get("id")
                if mid and mid not in member_map:
                    member_map[mid] = mem
            data.extend(workspace_members)

        return data

    def _normalize_issue(self, issue: Any, project_name: str, member_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Normalize issue/task info for retrieval."""
        priority = getattr(issue, "priority", None) or "none"
        state = getattr(issue, "state", None) or "không rõ trạng thái"
        start_date = getattr(issue, "start_date", None)
        target_date = getattr(issue, "target_date", None)
        assignees = self._normalize_assignees(issue)

        # Resolve assignee IDs to display/email if available
        assignees_resolved = []
        if member_map:
            raw_ids = getattr(issue, "assignees", None) or getattr(issue, "assignee", None) or []
            if isinstance(raw_ids, str):
                raw_ids = [raw_ids]
            for aid in raw_ids or []:
                mem = member_map.get(aid) or {}
                disp = mem.get("display_name") or mem.get("email") or aid
                email = mem.get("email")
                role = mem.get("role")
                extra = []
                if email:
                    extra.append(email)
                if role is not None:
                    extra.append(f"role={role}")
                if extra:
                    assignees_resolved.append(f"{disp} ({', '.join(extra)})")
                else:
                    assignees_resolved.append(disp)

        return {
            "type": "issue",
            "name": getattr(issue, "name", None) or "Task không tên",
            "description": getattr(issue, "description", None) or "Không có mô tả",
            "project_name": project_name,
            "priority": priority,
            "start_date": start_date or "không rõ",
            "target_date": target_date or "không rõ",
            "state_name": state,
            "assignees": assignees,
            "assignees_resolved": assignees_resolved,
        }

    def _normalize_assignees(self, issue: Any) -> List[str]:
        """Normalize assignee field to a list of names/emails."""
        assignee = getattr(issue, "assignee", None)
        if assignee is None:
            return []
        if isinstance(assignee, (list, tuple, set)):
            return [self._safe_string(item) for item in assignee if item]
        return [self._safe_string(assignee)]

    def _safe_string(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            name = value.get("name") or value.get("display_name")
            email = value.get("email")
            return name or email or str(value)
        return str(value)

    def _safe_list_members(
        self, plane_api: Any, project_id: Optional[str], project_name: str
    ) -> List[Dict[str, Any]]:
        members: List[Dict[str, Any]] = []
        seen: set = set()
        if not project_id:
            return members
        try:
            project_members = plane_api.list_project_members(project_id=project_id)
        except Exception as exc:
            logger.warning("Could not fetch members for project %s: %s", project_name, exc)
            return members

        for member in project_members:
            name = getattr(member, "display_name", None) or getattr(member, "email", None)
            email = getattr(member, "email", None) or (
                getattr(member, "member", {}) or {}
            ).get("email")
            role = getattr(member, "role", None) or "không rõ vai trò"
            key = (email, project_name)
            if key in seen:
                continue
            seen.add(key)
            members.append(
                {
                    "type": "member",
                    "name": name or "Thành viên không tên",
                    "email": email or "không rõ email",
                    "role": role,
                    "project_name": project_name,
                }
            )
        return members

    def _safe_workspace_members(self, plane_api: Any) -> List[Dict[str, Any]]:
        """Add workspace members once to improve recall, if available."""
        members: List[Dict[str, Any]] = []
        try:
            workspace_members = plane_api.list_members()
        except Exception:
            return members

        for member in workspace_members:
            name = getattr(member, "display_name", None) or getattr(member, "email", None)
            email = getattr(member, "email", None) or (
                getattr(member, "member", {}) or {}
            ).get("email")
            role = getattr(member, "role", None) or "không rõ vai trò"
            members.append(
                {
                    "type": "member",
                    "name": name or "Thành viên không tên",
                    "email": email or "không rõ email",
                    "role": role,
                    "project_name": "workspace",
                }
            )
        return members
