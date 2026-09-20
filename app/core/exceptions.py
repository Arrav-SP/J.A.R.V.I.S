"""Core exception definitions for JARVIS.

All exceptions within the JARVIS system inherit from JarvisError.
"""

from typing import Optional


class JarvisError(Exception):
    """Base exception for all JARVIS errors."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ConfigurationError(JarvisError):
    """Raised when configuration validation, file parsing, or environment setup fails."""
    pass


class InitializationError(JarvisError):
    """Raised when a core subsystem fails to initialize."""
    pass


class SystemStateError(JarvisError):
    """Raised when an operation is attempted in an invalid system state."""
    pass
