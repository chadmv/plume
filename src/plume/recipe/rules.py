"""Value rules a well-typed recipe must still meet: positive sizes, ordered times, known names."""

import re

from plume.recipe.errors import RecipeError
from plume.recipe.schema import ColorStop, Recipe

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MIN_FRAME_PX = 8


def check_rules(recipe: Recipe) -> None:
    """Raises RecipeError for the first rule the recipe breaks."""
    _check_domain(recipe)
    _check_time(recipe)
    _check_emitters(recipe)
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
    _at_least("time.frames", time.frames, 1)
    _at_least("time.substeps", time.substeps, 1)
    _at_least("time.warmup_s", time.warmup_s, 0.0)
    _at_least("solver.pressure_iterations", recipe.solver.pressure_iterations, 1)


def _check_emitters(recipe: Recipe) -> None:
    if not recipe.emitter:
        raise RecipeError("emitter needs at least one [[emitter]]")
    names = set()
    for index, emitter in enumerate(recipe.emitter):
        where = f"emitter[{index}]"
        if emitter.name in names:
            raise RecipeError(f"{where}.name {emitter.name!r} is used twice")
        names.add(emitter.name)
        if emitter.shape == "sphere":
            _positive(f"{where}.radius_m", emitter.radius_m)
        else:
            for axis, size in zip("xyz", emitter.size_m):
                _positive(f"{where}.size_m ({axis})", size)
        _between(f"{where}.edge_softness", emitter.edge_softness, 0.0, 1.0)
        if emitter.end_s <= emitter.start_s:
            raise RecipeError(f"{where}.end_s must be after start_s")
        _at_least(f"{where}.smoke_per_s", emitter.smoke_per_s, 0.0)
        if emitter.temperature_k != -1.0:
            _positive(f"{where}.temperature_k", emitter.temperature_k)
        _positive(f"{where}.noise.scale_m", emitter.noise.scale_m)
        _at_least(f"{where}.noise.strength", emitter.noise.strength, 0.0)


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


def _check_output(recipe: Recipe) -> None:
    _at_least("output.frame_px", recipe.output.frame_px, MIN_FRAME_PX)
    _at_least("output.columns", recipe.output.columns, 0)
    _at_least("preview.longest_axis_cells", recipe.preview.longest_axis_cells, 4)
    _at_least("preview.frames", recipe.preview.frames, 1)
    _at_least("preview.frame_px", recipe.preview.frame_px, MIN_FRAME_PX)


def _check_look(recipe: Recipe) -> None:
    look = recipe.look
    _between("look.ambient", look.ambient, 0.0, 1.0)
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
