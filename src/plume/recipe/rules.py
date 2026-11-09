"""Value rules a well-typed recipe must still meet: positive sizes, ordered times, known names."""

import math
import re

from plume.recipe.errors import RecipeError
from plume.recipe.schema import SEED_MAX, ColorStop, Recipe

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
PLAIN_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")
MIN_FRAME_PX = 8


def check_output_name(name: str) -> None:
    """Output names become file and folder names, so they must be one plain name: no paths, no `..`."""
    if not PLAIN_NAME.match(name) or ".." in name:
        raise RecipeError(f"output.name must be a plain name of letters, digits, '.', '_' and '-'; got {name!r} "
                          f"(when output.name is empty the recipe's file name is used)")


def check_rules(recipe: Recipe) -> None:
    """Raises RecipeError for the first rule the recipe breaks."""
    _between("seed", recipe.seed, 0, SEED_MAX)
    _check_domain(recipe)
    _check_time(recipe)
    _check_emitters(recipe)
    _check_forces(recipe)
    _check_camera(recipe)
    _check_render(recipe)
    _check_output(recipe)
    _check_look(recipe)


def _check_domain(recipe: Recipe) -> None:
    domain = recipe.domain
    _positive("domain.cell_m", domain.cell_m)
    for axis, size in zip("xyz", domain.size_m):
        _positive(f"domain.size_m ({axis})", size)
    _positive("domain.ambient_k", domain.ambient_k)


def _check_time(recipe: Recipe) -> None:
    time = recipe.time
    _positive("time.duration_s", time.duration_s)
    if not math.isfinite(time.frames * time.substeps / time.duration_s):
        raise RecipeError(f"time.duration_s is too small for {time.frames} frames, got {time.duration_s}")
    _at_least("time.frames", time.frames, 1)
    _at_least("time.substeps", time.substeps, 1)
    _at_least("time.warmup_s", time.warmup_s, 0.0)
    _at_least("solver.pressure_iterations", recipe.solver.pressure_iterations, 1)
    _at_least("solver.multigrid_cycles", recipe.solver.multigrid_cycles, 1)
    # One sweep a side is unstable next to open faces (measured in T2.2); two is the least that holds.
    _at_least("solver.multigrid_sweeps", recipe.solver.multigrid_sweeps, 2)
    _positive("solver.max_cells_per_step", recipe.solver.max_cells_per_step)
    _at_least("solver.max_substeps", recipe.solver.max_substeps, 1)


def _check_emitters(recipe: Recipe) -> None:
    if not recipe.emitter:
        raise RecipeError("emitter needs at least one [[emitter]]")
    names = set()
    for index, emitter in enumerate(recipe.emitter):
        where = f"emitter[{index}]"
        if emitter.name in names:
            raise RecipeError(f"{where}.name {emitter.name!r} is used twice")
        if not emitter.name or any(mark in emitter.name for mark in ".[]"):
            # --set and the viewer name an emitter's keys as emitter.<name>.<key>
            raise RecipeError(f"{where}.name must be a name without '.', '[' or ']'; got {emitter.name!r}")
        names.add(emitter.name)
        if emitter.shape == "sphere":
            _positive(f"{where}.radius_m", emitter.radius_m)
        else:
            for axis, size in zip("xyz", emitter.size_m):
                _positive(f"{where}.size_m ({axis})", size)
        _check_reaches_domain(recipe, where, emitter)
        _between(f"{where}.edge_softness", emitter.edge_softness, 0.0, 1.0)
        if emitter.end_s <= emitter.start_s:
            raise RecipeError(f"{where}.end_s must be after start_s")
        _at_least(f"{where}.smoke_per_s", emitter.smoke_per_s, 0.0)
        if emitter.temperature_k != -1.0:
            _positive(f"{where}.temperature_k", emitter.temperature_k)
        _positive(f"{where}.noise.scale_m", emitter.noise.scale_m)
        _at_least(f"{where}.noise.strength", emitter.noise.strength, 0.0)


def _check_reaches_domain(recipe: Recipe, where: str, emitter) -> None:
    """An emitter's shape must reach into the domain (faces included); one wholly outside emits nothing.

    The center may sit outside, as a ground source half sunk below the floor does. The check uses the
    requested `domain.size_m`, spanning -size/2..size/2 on x and z and 0..size on y; the grid rounds that
    size to whole cells, so a shape that only grazes a face can still miss every cell.
    """
    size = recipe.domain.size_m
    ranges = ((-size[0] / 2, size[0] / 2), (0.0, size[1]), (-size[2] / 2, size[2] / 2))
    reaches = (emitter.radius_m,) * 3 if emitter.shape == "sphere" else tuple(s / 2 for s in emitter.size_m)
    for axis, center, reach, (low, high) in zip("xyz", emitter.center_m, reaches, ranges):
        if center - reach > high or center + reach < low:
            raise RecipeError(f"{where} lies outside the domain on {axis}: its center {center:g} m reaches "
                              f"{reach:g} m, and the domain spans {low:g} to {high:g} m")


def _check_forces(recipe: Recipe) -> None:
    forces = recipe.forces
    _at_least("forces.drag_per_s", forces.drag_per_s, 0.0)
    _at_least("forces.vorticity_confinement", forces.vorticity_confinement, 0.0)
    _positive("forces.turbulence.scale_m", forces.turbulence.scale_m)
    _at_least("forces.turbulence.strength_mps2", forces.turbulence.strength_mps2, 0.0)
    _at_least("forces.turbulence.speed_mps", forces.turbulence.speed_mps, 0.0)
    if any(forces.wind_mps) and forces.drag_per_s == 0.0:
        raise RecipeError("forces.wind_mps needs forces.drag_per_s above 0: drag is what pulls the gas "
                          "toward the wind")


def _check_camera(recipe: Recipe) -> None:
    _between("camera.elevation_deg", recipe.camera.elevation_deg, -90.0, 90.0)
    names = [emitter.name for emitter in recipe.emitter]
    if recipe.camera.seat and recipe.camera.seat not in names:
        raise RecipeError(f"camera.seat {recipe.camera.seat!r} is not an emitter; emitters are "
                          f"{', '.join(names)}")


def _check_render(recipe: Recipe) -> None:
    render = recipe.render
    _at_least("render.px_per_cell", render.px_per_cell, 1.0)
    _positive("render.opacity_per_density", render.opacity_per_density)
    _between("render.smoke_hides_heat", render.smoke_hides_heat, 0.0, 1.0)
    _at_least("render.normal_blur_cells", render.normal_blur_cells, 0.0)
    _positive("render.normal_fade_thickness", render.normal_fade_thickness)
    _at_least("render.soften_px", render.soften_px, 0.0)
    _between("render.crop_margin", render.crop_margin, 0.0, 1.0)
    if not any(render.light_dir):
        raise RecipeError("render.light_dir must point somewhere; got (0, 0, 0)")
    _between("render.shade_fill", render.shade_fill, 0.0, 1.0)
    _positive("render.shade_fade_thickness", render.shade_fade_thickness)
    _positive("render.shade_neighborhood_px", render.shade_neighborhood_px)


def _check_output(recipe: Recipe) -> None:
    _at_least("output.frame_px", recipe.output.frame_px, MIN_FRAME_PX)
    _at_least("output.columns", recipe.output.columns, 0)
    _at_least("preview.longest_axis_cells", recipe.preview.longest_axis_cells, 4)
    _at_least("preview.frames", recipe.preview.frames, 1)
    _at_least("preview.frame_px", recipe.preview.frame_px, MIN_FRAME_PX)


def _check_look(recipe: Recipe) -> None:
    look = recipe.look
    _between("look.ambient", look.ambient, 0.0, 1.0)
    _between("look.shade_depth", look.shade_depth, 0.0, 1.0)
    _ramp("look.smoke_ramp", look.smoke_ramp)
    _ramp("look.emission_ramp", look.emission_ramp)
    _at_least("look.contact_px", look.contact_px, MIN_FRAME_PX)
    _color("look.backgrounds.neutral", look.backgrounds.neutral)
    _color("look.backgrounds.grass", look.backgrounds.grass)


def _ramp(key: str, stops: tuple[ColorStop, ...]) -> None:
    if not stops:
        raise RecipeError(f"{key} needs at least one stop")
    positions = [position for position, _ in stops]
    if positions != sorted(positions):
        raise RecipeError(f"{key} stop positions must increase")
    for index, (_, color) in enumerate(stops):
        _color(f"{key}[{index}]", color)


def _color(key: str, color: str) -> None:
    if not HEX_COLOR.match(color):
        raise RecipeError(f"{key} must be a color like \"#a1b2c3\", got {color!r}")


def _positive(key: str, value: float) -> None:
    if not value > 0:
        raise RecipeError(f"{key} must be greater than 0, got {value}")


def _at_least(key: str, value: float, minimum: float) -> None:
    if value < minimum:
        raise RecipeError(f"{key} must be at least {minimum}, got {value}")


def _between(key: str, value: float, low: float, high: float) -> None:
    if not low <= value <= high:
        raise RecipeError(f"{key} must be between {low} and {high}, got {value}")
