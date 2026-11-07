"""The JSON written beside each sheet: the contract a game reads, keys in a fixed order."""

import json
from dataclasses import dataclass
from pathlib import Path

DECIMALS = 6


@dataclass(frozen=True)
class SheetInfo:
    frames: int
    columns: int
    frame_px: int
    fps: float
    frame_m: float
    seat: tuple[float, float]
    channels: str  # the recipe's `output.channels`, one of the schema's layouts
    source: str
    tool: str
    written_by: str


def sheet_json_text(info: SheetInfo) -> str:
    """The JSON text, keys in the contract's order, floats rounded, 2-space indent, trailing newline."""
    table = {
        "frames": info.frames,
        "columns": info.columns,
        "frame_px": info.frame_px,
        "fps": round(info.fps, DECIMALS),
        "frame_m": round(info.frame_m, DECIMALS),
        "seat": [round(info.seat[0], DECIMALS), round(info.seat[1], DECIMALS)],
        "channels": info.channels,
        "source": info.source,
        "tool": info.tool,
        "written_by": info.written_by,
    }
    return json.dumps(table, indent=2) + "\n"


def source_path(recipe_path: Path) -> str:
    """The recipe path relative to its git repository's root, with forward slashes; as given if none."""
    absolute = recipe_path.resolve()
    for folder in absolute.parents:
        if (folder / ".git").exists():
            return absolute.relative_to(folder).as_posix()
    return recipe_path.as_posix()
