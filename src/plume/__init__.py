"""Plume: fire, smoke and explosion flipbooks from text recipes."""

__version__ = "0.1.0"
TOOL_NAME = "plume"


def tool_label() -> str:
    """The tool's name and version, as written into every sheet's JSON."""
    return f"{TOOL_NAME} {__version__}"
