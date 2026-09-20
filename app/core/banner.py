"""Banner and status display utilities for JARVIS."""


def get_status_text(mode: str = "terminal", status: str = "ready") -> str:
    """Return the exact status block defined in the roadmap specification."""
    return f"JARVIS CORE ONLINE\nMode: {mode}\nStatus: {status}"


def get_banner(mode: str = "terminal", status: str = "ready") -> str:
    """Return an aesthetically pleasing terminal startup banner."""
    lines = [
        "=" * 50,
        get_status_text(mode=mode, status=status),
        "=" * 50,
    ]
    return "\n".join(lines)


def get_shutdown_banner() -> str:
    """Return clean shutdown message."""
    return "\n" + "=" * 50 + "\nJARVIS CORE OFFLINE\n" + "=" * 50
