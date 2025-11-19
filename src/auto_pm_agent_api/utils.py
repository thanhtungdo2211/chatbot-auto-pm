"""Utility functions for the application."""

import logging
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
