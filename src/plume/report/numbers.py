"""The numbers file: a summary block, then one fixed-width row of measurements per frame.

Measured from the quantized sheet frames, so the numbers describe exactly what Petri gets.
"""

from dataclasses import dataclass

import numpy as np

COVERED_LEVEL = 8  # G byte at which a pixel counts as visibly covered
FADE_FRACTION = 0.1
KEY_WIDTH = 18
COLUMNS = ("frame", "time_s", "coverage", "left", "top", "right", "bottom", "mean_heat", "mean_thick",
           "total_thick", "peak_heat")
WIDTHS = (5, 8, 9, 7, 7, 7, 7, 10, 11, 12, 10)


@dataclass(frozen=True)
class FrameNumbers:
    frame: int
    time_s: float
    coverage: float
    box: tuple[float, float, float, float] | None  # left, top, right, bottom as frame fractions
    mean_heat: float
    mean_thick: float
    total_thick: float
    peak_heat: float


@dataclass(frozen=True)
class RunFacts:
    recipe: str
    backend: str
    grid: str
    fps: float
    frame_m: float
    heat_divisor: float


def measure(frames: list[np.ndarray], fps: float) -> list[FrameNumbers]:
    """Per-frame measurements of quantized RGBA frames."""
    return [_measure_frame(index, frame, (index + 1) / fps) for index, frame in enumerate(frames)]


def peak_and_fade(rows: list[FrameNumbers]) -> tuple[int, int | None]:
    """The frame of greatest total thickness, and the first later frame under 10 percent of it."""
    totals = [row.total_thick for row in rows]
    peak = int(np.argmax(totals))
    for row in rows[peak + 1:]:
        if row.total_thick < FADE_FRACTION * totals[peak]:
            return peak, row.frame
    return peak, None


def numbers_text(rows: list[FrameNumbers], facts: RunFacts) -> str:
    """The whole file's text."""
    peak, fade = peak_and_fade(rows)
    summary = [
        ("recipe", facts.recipe),
        ("backend", facts.backend),
        ("grid", facts.grid),
        ("frames", str(len(rows))),
        ("fps", f"{facts.fps:.6f}"),
        ("frame_m", f"{facts.frame_m:.6f}"),
        ("heat_divisor", f"{facts.heat_divisor:.6f} K m"),
        ("peak_frame", str(peak)),
        ("fade_frame", "never" if fade is None else str(fade)),
    ]
    lines = [f"{key:<{KEY_WIDTH}}{value}" for key, value in summary]
    lines.append("")
    lines.append(_row_text(COLUMNS))
    lines.extend(_row_text(_row_values(row)) for row in rows)
    return "\n".join(lines) + "\n"


def _measure_frame(index: int, frame: np.ndarray, time_s: float) -> FrameNumbers:
    heat = frame[..., 0].astype(np.float64) / 255.0
    thickness = frame[..., 1].astype(np.float64) / 255.0
    covered = frame[..., 1] >= COVERED_LEVEL
    size = frame.shape[0]
    box = None
    if covered.any():
        rows = np.nonzero(covered.any(axis=1))[0]
        columns = np.nonzero(covered.any(axis=0))[0]
        box = (columns[0] / size, rows[0] / size, (columns[-1] + 1) / size, (rows[-1] + 1) / size)
    return FrameNumbers(
        frame=index,
        time_s=time_s,
        coverage=float(covered.mean()),
        box=box,
        mean_heat=float(heat[covered].mean()) if covered.any() else 0.0,
        mean_thick=float(thickness[covered].mean()) if covered.any() else 0.0,
        total_thick=float(thickness.sum()),
        peak_heat=float(heat.max()),
    )


def _row_values(row: FrameNumbers) -> list[str]:
    box = [f"{value:.4f}" for value in row.box] if row.box else ["-"] * 4
    return [str(row.frame), f"{row.time_s:.4f}", f"{row.coverage:.4f}", *box, f"{row.mean_heat:.4f}",
            f"{row.mean_thick:.4f}", f"{row.total_thick:.4f}", f"{row.peak_heat:.4f}"]


def _row_text(values) -> str:
    return " ".join(f"{value:>{width}}" for value, width in zip(values, WIDTHS)).rstrip()


def read_numbers(text: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Parses a numbers file back into its summary and rows (for tests and tools)."""
    head, _, table = text.partition("\n\n")
    summary = {}
    for line in head.splitlines():
        key, _, value = line.partition(" ")
        summary[key] = value.strip()
    lines = table.strip().splitlines()
    names = lines[0].split()
    return summary, [dict(zip(names, line.split())) for line in lines[1:]]
