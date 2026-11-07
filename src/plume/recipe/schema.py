"""The recipe schema: every key a recipe may hold, with its type, unit, default and meaning.

This is the single source for recipe keys. The loader validates against it, the settings log writes from
it, and `docs/recipe-reference.md` is generated from it. A field's Python type is its recipe type; its
metadata carries the unit, the description and, for text keys, the allowed choices.
"""

import dataclasses
from dataclasses import dataclass
from typing import Any

Vec3 = tuple[float, float, float]
ColorStop = tuple[float, str]

REQUIRED = dataclasses.MISSING
FACE_KINDS = ("closed", "open")


def setting(default: Any, unit: str, doc: str, choices: tuple[str, ...] = ()) -> Any:
    """Declares one recipe key. Pass `REQUIRED` as the default for a key the recipe must give."""
    metadata = {"unit": unit, "doc": doc, "choices": choices}
    if isinstance(default, (list, dict)):
        raise TypeError("use tuples for sequence defaults so settings stay immutable")
    return dataclasses.field(default=default, metadata=metadata)


def section(doc: str) -> Any:
    """Declares a nested table. The loader always builds it, from an empty table when absent."""
    return dataclasses.field(default=None, metadata={"unit": "", "doc": doc, "choices": (), "section": True})


@dataclass(frozen=True, kw_only=True)
class FaceSettings:
    bottom: str = setting("closed", "", "Floor of the domain (y minimum).", FACE_KINDS)
    top: str = setting("open", "", "Ceiling of the domain (y maximum).", FACE_KINDS)
    left: str = setting("open", "", "x minimum face.", FACE_KINDS)
    right: str = setting("open", "", "x maximum face.", FACE_KINDS)
    back: str = setting("open", "", "z minimum face, away from the default camera.", FACE_KINDS)
    front: str = setting("open", "", "z maximum face, toward the default camera.", FACE_KINDS)


@dataclass(frozen=True, kw_only=True)
class DomainSettings:
    size_m: Vec3 = setting(REQUIRED, "m", "Width, height and depth of the simulation box. Its origin is the "
                                          "center of the floor.")
    cell_m: float = setting(REQUIRED, "m", "Edge length of one grid cell.")
    ambient_k: float = setting(293.0, "K", "Temperature of the surrounding air.")
    faces: FaceSettings = section("Each face of the box is `closed` (a solid wall) or `open` (material "
                                  "leaves freely).")


@dataclass(frozen=True, kw_only=True)
class TimeSettings:
    duration_s: float = setting(REQUIRED, "s", "Effect time covered by the flipbook.")
    frames: int = setting(64, "", "Number of flipbook frames, evenly spaced over the duration.")
    substeps: int = setting(3, "", "Simulation steps per frame.")
    warmup_s: float = setting(0.0, "s", "Simulated time before frame 0.")


@dataclass(frozen=True, kw_only=True)
class NoiseSettings:
    scale_m: float = setting(0.1, "m", "Size of the emitter's breakup pattern.")
    strength: float = setting(0.0, "", "How strongly the pattern breaks up the emitter; 0 for none.")


@dataclass(frozen=True, kw_only=True)
class EmitterSettings:
    name: str = setting(REQUIRED, "", "Name, used by `camera.seat`.")
    shape: str = setting("sphere", "", "Emitter shape.", ("sphere", "box"))
    center_m: Vec3 = setting(REQUIRED, "m", "Center of the shape.")
    radius_m: float = setting(0.0, "m", "Radius of a sphere.")
    size_m: Vec3 = setting((0.0, 0.0, 0.0), "m", "Width, height and depth of a box.")
    edge_softness: float = setting(0.3, "", "Outer fraction of the shape over which emission fades to 0.")
    start_s: float = setting(0.0, "s", "Effect time the emitter starts.")
    end_s: float = setting(REQUIRED, "s", "Effect time the emitter stops.")
    smoke_per_s: float = setting(0.0, "1/s", "Smoke density added per second at full coverage.")
    temperature_k: float = setting(-1.0, "K", "Temperature the emitter holds its cells at; -1 means ambient.")
    velocity_mps: Vec3 = setting((0.0, 0.0, 0.0), "m/s", "Velocity the emitter holds its cells at.")
    velocity_mode: str = setting("fixed", "", "`fixed` uses `velocity_mps`; `outward` pushes away from the "
                                              "center at the length of `velocity_mps`.", ("fixed", "outward"))
    noise: NoiseSettings = section("Seeded breakup of the emitter's shape.")


@dataclass(frozen=True, kw_only=True)
class ForceSettings:
    gravity_mps2: float = setting(9.81, "m/s^2", "Strength of gravity.")
    heat_buoyancy: float = setting(1.0, "", "Lift from heat; 1 is ideal-gas buoyancy.")
    smoke_weight: float = setting(0.0, "", "Sink from smoke density, as a fraction of gravity per unit "
                                           "density.")


@dataclass(frozen=True, kw_only=True)
class DissipationSettings:
    smoke_per_s: float = setting(0.0, "1/s", "Rate smoke fades.")
    cooling_per_s: float = setting(0.0, "1/s", "Rate temperature relaxes toward ambient.")


@dataclass(frozen=True, kw_only=True)
class SolverSettings:
    pressure_solver: str = setting("multigrid", "", "How the pressure is solved: `multigrid` (fixed V-cycles) or "
                                                    "`gauss_seidel` (slice 1's fixed sweeps).",
                                   ("multigrid", "gauss_seidel"))
    pressure_iterations: int = setting(60, "", "Red-black Gauss-Seidel sweeps per pressure solve, for "
                                               "`gauss_seidel`.")
    multigrid_cycles: int = setting(2, "", "Multigrid V-cycles per pressure solve.")
    multigrid_sweeps: int = setting(2, "", "Smoothing sweeps before and after each multigrid level's "
                                           "correction.")


@dataclass(frozen=True, kw_only=True)
class CameraSettings:
    elevation_deg: float = setting(0.0, "deg", "How far the camera looks down; 0 is a level side view.")
    azimuth_deg: float = setting(0.0, "deg", "Orbit around the vertical axis, counterclockwise seen from "
                                             "above; 0 looks along -z.")
    seat: str = setting("", "", "Emitter whose center is the seat point; empty means the first emitter.")


@dataclass(frozen=True, kw_only=True)
class RenderSettings:
    px_per_cell: float = setting(2.0, "", "Pixels per cell when rendering the whole domain view.")
    opacity_per_density: float = setting(4.0, "1/m", "Opacity per unit smoke density per meter of ray.")
    glow_start_k: float = setting(600.0, "K", "Temperature where heat starts to glow.")
    smoke_hides_heat: float = setting(1.0, "", "How much smoke in front hides glow behind it, 0 to 1.")
    normal_blur_cells: float = setting(1.5, "cells", "Blur applied to smoke before taking surface normals.")
    normal_fade_thickness: float = setting(0.1, "", "Below this thickness, normals fade to face the camera.")
    soften_px: float = setting(0.75, "px", "Gaussian blur on the final frames.")
    crop_margin: float = setting(0.04, "", "Empty margin around the content, as a fraction of the frame.")


@dataclass(frozen=True, kw_only=True)
class OutputSettings:
    name: str = setting("", "", "Output name; empty means the recipe file's name.")
    frame_px: int = setting(256, "px", "Width and height of one frame.")
    columns: int = setting(0, "", "Frames per sheet row; 0 means the smallest square grid.")


@dataclass(frozen=True, kw_only=True)
class PreviewSettings:
    longest_axis_cells: int = setting(48, "cells", "Cells along the domain's longest axis in --preview.")
    frames: int = setting(16, "", "Frames in --preview; substeps rise so each step is as long as a full run's.")
    frame_px: int = setting(128, "px", "Frame size in --preview.")


@dataclass(frozen=True, kw_only=True)
class BackgroundSettings:
    neutral: str = setting("#808080", "sRGB", "Background of contact_neutral.png.")
    grass: str = setting("#aac476", "sRGB", "Background of contact_grass.png (Petri's mid grass).")


@dataclass(frozen=True, kw_only=True)
class LookSettings:
    ambient: float = setting(0.65, "", "Light every smoke surface gets, 0 to 1.")
    sun_dir: Vec3 = setting((-0.5, 0.7, 0.5), "", "Direction toward the sun in camera space (x right, y up, "
                                                  "z toward the camera).")
    smoke_ramp: tuple[ColorStop, ...] = setting(
        ((0.0, "#aea193"), (0.4, "#bc9c84"), (0.75, "#dca07a"), (1.0, "#f5b47e")), "",
        "Smoke color by heat, as [position, sRGB] stops (cool end from the reference's sunlit smoke).")
    emission_ramp: tuple[ColorStop, ...] = setting(
        ((0.0, "#000000"), (0.2, "#3a0c04"), (0.5, "#c4441a"), (0.8, "#ff9a3a"), (1.0, "#fff2c2")), "",
        "Glow color added by heat, as [position, sRGB] stops.")
    contact_px: int = setting(128, "px", "Thumbnail size on the contact sheets.")
    backgrounds: BackgroundSettings = section("Contact sheet backgrounds.")


@dataclass(frozen=True, kw_only=True)
class Recipe:
    extends: str = setting("", "", "Parent recipe this one builds on, as a path relative to this file. Tables "
                                   "merge key by key; any other value, `[[emitter]]` included, replaces the "
                                   "parent's. Empty in a resolved recipe.")
    seed: int = setting(0, "", "Seed for every random choice in the run.")
    domain: DomainSettings = section("The simulation box.")
    time: TimeSettings = section("Effect time and frames.")
    emitter: tuple[EmitterSettings, ...] = setting(REQUIRED, "", "Sources of smoke, heat and motion.")
    forces: ForceSettings = section("Forces on the gas.")
    dissipation: DissipationSettings = section("How smoke and heat fade.")
    solver: SolverSettings = section("Solver controls.")
    camera: CameraSettings = section("The orthographic camera.")
    render: RenderSettings = section("Turning the volume into sheet channels.")
    output: OutputSettings = section("The sheet's size and name.")
    preview: PreviewSettings = section("Overrides used by --preview.")
    look: LookSettings = section("Contact sheet colors; never affects the sheet.")


def field_info(field: dataclasses.Field) -> dict[str, Any]:
    """The unit, description, allowed choices and section flag of a schema field."""
    return {
        "unit": field.metadata.get("unit", ""),
        "doc": field.metadata.get("doc", ""),
        "choices": field.metadata.get("choices", ()),
        "section": field.metadata.get("section", False),
    }
