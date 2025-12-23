"""Utility functions for the application."""

import logging
import os
import re
from typing import Any, Dict, List
from datetime import datetime


def setup_logging(log_level: str = "INFO", log_file: str = "app.log") -> None:
    """
    Setup application logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8")
        ]
    )


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime object to string.
    
    Args:
        dt: Datetime object
        format_str: Format string
        
    Returns:
        Formatted datetime string
    """
    return dt.strftime(format_str)


def safe_dict_get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary values.
    
    Args:
        data: Dictionary to access
        *keys: Sequence of keys to traverse
        default: Default value if key not found
        
    Returns:
        Value at the nested key or default
        
    Example:
        safe_dict_get(data, "user", "profile", "name", default="Unknown")
    """
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
            if result is None:
                return default
        else:
            return default
    return result


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        lst: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunked lists
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def normalize_string(text: str) -> str:
    """
    Normalize a string by removing extra whitespace and converting to lowercase.
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
    """
    return " ".join(text.strip().lower().split())


def is_affirmative(text: str) -> bool:
    """
    Check if text contains affirmative response.
    
    Args:
        text: Text to check
        
    Returns:
        True if affirmative, False otherwise
    """
    affirmative_words = [
        "có", "yes", "ok", "okay", "đồng ý", "chắc chắn",
        "vâng", "oke", "được", "đúng", "ừ", "uh"
    ]
    normalized = normalize_string(text)
    return any(word in normalized for word in affirmative_words)


def validate_email(email: str) -> bool:
    """
    Basic email validation.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid format, False otherwise
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def markdown_to_text(text: str) -> str:
    """
    Convert a subset of Markdown to plain text for clients that don't render Markdown.

    This is intentionally lightweight (no external deps) and focuses on the most common
    Markdown constructs emitted by LLMs: emphasis, code fences, inline code, headings,
    links, blockquotes.
    """
    if not text:
        return text

    out = str(text)
    out = out.replace("\r\n", "\n").replace("\r", "\n")

    # Remove code fences but keep code content
    out = re.sub(r"```[^\n]*\n(.*?)```", r"\1", out, flags=re.DOTALL)
    out = re.sub(r"```(.*?)```", r"\1", out, flags=re.DOTALL)

    # Inline code
    out = re.sub(r"`([^`]+)`", r"\1", out)

    # Images: ![alt](url) -> alt (url)
    out = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\1 (\2)", out)

    # Links: [text](url) -> text (url)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", out)

    # Headings: # Title -> Title
    out = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", out)

    # Blockquotes: > quote -> quote
    out = re.sub(r"(?m)^\s{0,3}>\s?", "", out)

    # Horizontal rules
    out = re.sub(r"(?m)^\s{0,3}(-{3,}|\*{3,}|_{3,})\s*$", "", out)

    # Emphasis (bold/italic/strikethrough) - keep inner text
    for _ in range(3):
        prev = out
        out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)
        out = re.sub(r"__(.+?)__", r"\1", out)
        out = re.sub(r"~~(.+?)~~", r"\1", out)
        # Single * / _ emphasis (avoid words_with_underscore)
        out = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", out)
        out = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", out)
        if out == prev:
            break

    # Strip trivial HTML tags if present
    out = re.sub(r"<[^>]+>", "", out)

    # Cleanup excessive blank lines
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def format_chat_response(text: str) -> str:
    """
    Normalize chatbot output. Default behavior converts Markdown → plain text.

    Toggle by env:
    - RESPONSE_FORMAT=markdown   => keep original
    - RESPONSE_FORMAT=text       => convert to plain text (default)
    """
    fmt = (os.getenv("RESPONSE_FORMAT") or "text").strip().lower()
    if fmt in {"markdown", "md"}:
        return text or ""
    return markdown_to_text(text or "")
