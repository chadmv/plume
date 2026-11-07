"""`plume run`: the four pipeline steps (load, simulate and capture, assemble, report) for one recipe."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import warp as wp

from plume import tool_label
from plume.cli.summary import print_summary
from plume.recipe.derived import Derived, derive
from plume.recipe.load import load_recipe_with_origin
from plume.recipe.schema import Recipe
from plume.recipe.serialize import recipe_to_toml
from plume.recipe.variation import RecipeOrigin
from plume.render.camera import DomainView, make_camera, make_domain_view
from plume.render.frame_renderer import FrameRenderer
from plume.report.channels import channel_strip
from plume.report.contact import contact_sheet
from plume.report.numbers import RunFacts, measure, numbers_text
from plume.report.timing import StageTimer
from plume.sheet.assemble import AssembledFrames, assemble
from plume.sheet.pack import pack, write_png
from plume.sheet.sheet_json import SheetInfo, sheet_json_text, source_path
from plume.sim.device import init_device
from plume.sim.run import simulate


@dataclass(frozen=True)
class RunResult:
    out_dir: Path
    files: dict[str, Path]
    recipe: Recipe
    derived: Derived
    device: str
    assembled: AssembledFrames
    numbers: str
    timer: StageTimer


def run_recipe(recipe_path: Path, preview: bool, device: str, out: str | None, command: str,
               sets: tuple[str, ...] = ()) -> RunResult:
    """Runs a recipe end to end, writes every output, prints the summary, and returns what it wrote."""
    timer = StageTimer()
    with timer.stage("load"):
        recipe, origin = load_recipe_with_origin(recipe_path, preview=preview, sets=sets)
        derived = derive(recipe)
        device_name = init_device(device)
    view = make_domain_view(make_camera(recipe.camera.elevation_deg, recipe.camera.azimuth_deg),
                            derived.domain_min_m, derived.size_m, recipe.domain.cell_m, recipe.render.px_per_cell)
    raw_frames = _simulate_and_capture(recipe, derived, device_name, view, timer)
    with timer.stage("assemble"):
        assembled = assemble(raw_frames, view, _seat_point(recipe), recipe.output.frame_px,
                             recipe.render.soften_px, recipe.render.crop_margin)
    with timer.stage("report"):
        out_dir = _out_dir(recipe, out, preview)
        files, numbers = _write_outputs(out_dir, recipe, derived, device_name, assembled,
                                        source_path(recipe_path), command, origin)
    timer_path = out_dir / "timing.txt"
    timer_path.write_text(timer.text(), newline="\n")
    files["timing"] = timer_path
    result = RunResult(out_dir, files, recipe, derived, device_name, assembled, numbers, timer)
    print_summary(result)
    return result


def _simulate_and_capture(recipe: Recipe, derived: Derived, device: str, view: DomainView,
                          timer: StageTimer) -> list[np.ndarray]:
    renderer = FrameRenderer(view, recipe.render, derived.cells, device)
    raw_frames = []

    def capture(frame, grid):
        wp.synchronize_device(device)
        with timer.stage("render"):
            raw_frames.append(renderer.render(grid))

    with timer.stage("simulate"):
        simulate(recipe, derived, device, capture)
        wp.synchronize_device(device)
    timer.exclude("simulate", "render")
    return raw_frames


def _seat_point(recipe: Recipe) -> np.ndarray:
    emitter = next(e for e in recipe.emitter if e.name == recipe.camera.seat)
    return np.array(emitter.center_m, dtype=np.float64)


def _out_dir(recipe: Recipe, out: str | None, preview: bool) -> Path:
    base = Path(out) if out else Path("out") / recipe.output.name
    folder = base / "preview" if preview else base
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _write_outputs(out_dir: Path, recipe: Recipe, derived: Derived, device: str, assembled: AssembledFrames,
                   source: str, command: str, origin: RecipeOrigin) -> tuple[dict[str, Path], str]:
    name = recipe.output.name
    columns = recipe.output.columns
    files = {
        "sheet": out_dir / f"{name}.png",
        "json": out_dir / f"{name}.json",
        "contact_neutral": out_dir / "contact_neutral.png",
        "contact_grass": out_dir / "contact_grass.png",
        "channels": out_dir / "channels.png",
        "numbers": out_dir / "numbers.txt",
        "settings": out_dir / "settings.toml",
    }
    frames = assembled.frames
    write_png(files["sheet"], pack(frames, columns))
    info = SheetInfo(frames=len(frames), columns=columns, frame_px=recipe.output.frame_px, fps=derived.fps,
                     frame_m=assembled.frame_m, seat=assembled.seat, source=source, tool=tool_label(),
                     written_by=command)
    files["json"].write_text(sheet_json_text(info), newline="\n")
    look = recipe.look
    contact_sheet(frames, columns, look.backgrounds.neutral, look).save(files["contact_neutral"], compress_level=6)
    contact_sheet(frames, columns, look.backgrounds.grass, look).save(files["contact_grass"], compress_level=6)
    channel_strip(frames, look).save(files["channels"], compress_level=6)
    nx, ny, nz = derived.cells
    facts = RunFacts(recipe=source, backend=device, grid=f"{nx} x {ny} x {nz} cells of {recipe.domain.cell_m:.6f} m",
                     fps=derived.fps, frame_m=assembled.frame_m, heat_divisor=assembled.heat_divisor)
    numbers = numbers_text(measure(frames, derived.fps), facts)
    files["numbers"].write_text(numbers, newline="\n")
    files["settings"].write_text(recipe_to_toml(recipe, derived, device, origin), newline="\n")
    return files, numbers
