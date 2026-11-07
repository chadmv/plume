"""The short summary `plume run` prints: where everything went and the few numbers that steer the next run."""

from typing import TYPE_CHECKING

from plume import tool_label
from plume.report.numbers import read_numbers

if TYPE_CHECKING:
    from plume.cli.run import RunResult


def print_summary(result: "RunResult") -> None:
    summary, _ = read_numbers(result.numbers)
    recipe = result.recipe
    nx, ny, nz = result.derived.cells
    columns = recipe.output.columns
    rows = -(-recipe.time.frames // columns)
    print(f"{tool_label()}: wrote {result.out_dir.as_posix()}/")
    for key, path in result.files.items():
        print(f"  {key:<16}{path.name}")
    print(f"sheet    {columns} x {rows} frames of {recipe.output.frame_px} px, {recipe.time.frames} frames "
          f"at {result.derived.fps:.3f} fps")
    print(f"grid     {nx} x {ny} x {nz} cells of {recipe.domain.cell_m:.4f} m on {result.device}")
    print(f"time     {result.timer.total():.2f} s ({_stage_list(result.timer.seconds)})")
    print(f"numbers  peak_frame {summary['peak_frame']}, fade_frame {summary['fade_frame']}, "
          f"frame_m {result.assembled.frame_m:.4f}, seat ({result.assembled.seat[0]:.3f}, "
          f"{result.assembled.seat[1]:.3f})")


def _stage_list(seconds: dict[str, float]) -> str:
    return ", ".join(f"{name} {value:.2f}" for name, value in seconds.items())
