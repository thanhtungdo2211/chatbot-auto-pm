"""Domain exceptions for the application."""


class DomainException(Exception):
    """Base exception for domain layer."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(DomainException):
    """Raised when domain validation fails."""
    pass


class MemoryError(DomainException):
    """Raised when memory operations fail."""
    pass


class LLMError(DomainException):
    """Raised when LLM operations fail."""
    pass


class ProjectError(DomainException):
    """Raised when project operations fail."""
    pass


class SessionError(DomainException):
    """Raised when session operations fail."""
    pass
