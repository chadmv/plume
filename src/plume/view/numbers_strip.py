"""The numbers strip under the viewport (spec V5): coverage, mean thickness and peak heat per frame, with the
playhead, and marks on frames where the smoke reaches an open face or the ceiling and frames whose block of
steps the CFL cap split.

The numbers are `report/numbers.py`'s `measure` of the sheet's frames, the numbers `numbers.txt` holds, so
they show once a run's sheet is assembled. Edge marks come from the run as frames land (`LiveRun.edges`),
step-cap marks from the step log once the run is done (or a sheet folder's `settings.toml`).
"""

from dataclasses import dataclass, field

import numpy as np

from plume.report.numbers import FrameNumbers, measure

SERIES = (("coverage", "coverage"), ("mean thickness", "mean_thick"), ("peak heat", "peak_heat"))
STRIP_PX = 120
EDGE_COLOR = (1.0, 0.6, 0.2, 0.6)
CAPPED_COLOR = (0.9, 0.3, 0.9, 0.6)
PLAYHEAD_COLOR = (1.0, 1.0, 1.0, 0.9)


@dataclass(frozen=True)
class StripData:
    """What the strip plots: one value per frame for each series (empty before the sheet exists), the faces
    each marked frame's smoke reached, and the frames the step cap split."""

    frames: int
    series: dict[str, np.ndarray] = field(default_factory=dict)
    edges: dict[int, tuple[str, ...]] = field(default_factory=dict)
    capped: tuple[int, ...] = ()


def series_of(rows: list[FrameNumbers]) -> dict[str, np.ndarray]:
    """The strip's series from `measure`'s rows."""
    return {label: np.array([getattr(row, name) for row in rows], dtype=np.float64) for label, name in SERIES}


def strip_data(frames: int, sheet_frames: list[np.ndarray] | None, fps: float,
               edges: dict[int, tuple[str, ...]] | None = None,
               steps_per_frame: tuple[int, ...] | None = None, base_steps_per_frame: int = 0) -> StripData:
    """The strip for a run or a sheet: series from the quantized sheet frames when there are any, edge marks
    for frames that reached a face, step-cap marks for frames that took more steps than the base."""
    series = series_of(measure(sheet_frames, fps)) if sheet_frames else {}
    return StripData(frames=frames, series=series,
                     edges={frame: faces for frame, faces in (edges or {}).items() if faces},
                     capped=capped_frames(steps_per_frame, base_steps_per_frame))


def capped_frames(steps_per_frame: tuple[int, ...] | None, base_steps_per_frame: int) -> tuple[int, ...]:
    """The frames whose block the CFL cap split into more steps than the recipe's substeps."""
    if not steps_per_frame:
        return ()
    return tuple(frame for frame, steps in enumerate(steps_per_frame) if steps > base_steps_per_frame)


def frame_tooltip(data: StripData, frame: int) -> str:
    """The hover text for a frame: its numbers and its marks."""
    lines = [f"frame {frame}"]
    for label, values in data.series.items():
        if frame < len(values):
            lines.append(f"{label} {values[frame]:.4f}")
    if frame in data.edges:
        lines.append("smoke reaches " + ", ".join(data.edges[frame]))
    if frame in data.capped:
        lines.append("the step cap added steps")
    return "\n".join(lines)


def draw_strip(data: StripData, playhead: int, width: float) -> int | None:
    """Draws the strip with ImPlot; returns a frame when the playhead line was dragged to it, else None."""
    from imgui_bundle import imgui, implot

    moved = None
    flags = implot.Flags_.no_title | implot.Flags_.no_menus | implot.Flags_.no_box_select | implot.Flags_.no_mouse_text
    if not implot.begin_plot("##numbers", imgui.ImVec2(width, STRIP_PX), flags):
        return None
    axis_flags = implot.AxisFlags_.lock
    implot.setup_axes("", "", axis_flags | implot.AxisFlags_.no_tick_labels, axis_flags)
    implot.setup_axis_limits(implot.ImAxis_.x1, -0.5, max(data.frames, 1) - 0.5, implot.Cond_.always)
    implot.setup_axis_limits(implot.ImAxis_.y1, 0.0, 1.0, implot.Cond_.always)
    implot.setup_legend(implot.Location_.north_east, implot.LegendFlags_.horizontal)
    frames = np.arange(data.frames, dtype=np.float64)
    for label, values in data.series.items():
        implot.plot_line(label, frames[:len(values)], values)
    if data.edges:
        implot.plot_inf_lines("reaches a face", np.array(sorted(data.edges), dtype=np.float64),
                              _line_spec(implot, imgui, EDGE_COLOR))
    if data.capped:
        implot.plot_inf_lines("step cap", np.array(data.capped, dtype=np.float64),
                              _line_spec(implot, imgui, CAPPED_COLOR))
    if not data.series:
        implot.plot_text("the numbers show once the sheet is assembled", data.frames / 2, 0.5)
    changed, position, _, _, _ = implot.drag_line_x(0, float(playhead), imgui.ImVec4(*PLAYHEAD_COLOR), 1.5)
    if changed:
        moved = int(round(min(max(position, 0.0), data.frames - 1)))
    if implot.is_plot_hovered():
        mouse = implot.get_plot_mouse_pos()
        frame = int(round(mouse.x))
        if 0 <= frame < data.frames:
            imgui.set_tooltip(frame_tooltip(data, frame))
    implot.end_plot()
    return moved


def _line_spec(implot, imgui, color):
    spec = implot.Spec()
    spec.line_color = imgui.ImVec4(*color)
    return spec
