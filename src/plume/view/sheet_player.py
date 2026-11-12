"""The Sheet tab (spec V2 and section 4.3): the assembled flipbook played on a card facing the camera, the way
a game shows it, over the chosen background.

The card's side is the sheet's `frame_m` and its `seat` point (a fraction of the frame, from the top left)
sits on a world point: the seat emitter's center for a recipe (so at Home the card covers the volume's
smoke), the origin for a sheet folder opened alone. The cell is the contact sheets' own composite
(`report/contact.py`) over the background; the tab is drawn on the host as one image, the background with
the card resized bilinearly to its place on screen (only its visible part), so the screen, stills and clips
share one drawing. Playback steps whole sheet frames at the sheet's fps; there is no blending.

A sheet folder is `plume run`'s output folder (or any folder holding one sheet and its JSON); its look comes
from the `settings.toml` beside it, else from the schema's defaults (and `look_note` says so).
"""

import json
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from plume.recipe.errors import RecipeError
from plume.recipe.load import load_recipe
from plume.recipe.schema import LookSettings, Recipe, RenderSettings
from plume.render.camera import DomainView
from plume.report.color import hex_to_linear, to_srgb_bytes
from plume.report.composite import SheetLook, sheet_look
from plume.report.contact import composited_image
from plume.sheet.assemble import AssembledFrames, seat_point
from plume.view.navigation import ViewCamera

SETTINGS_FILE = "settings.toml"
SHEET_KEYS = ("frames", "columns", "frame_px", "fps", "frame_m", "seat", "channels")


class SheetFolderError(Exception):
    """The folder does not hold one readable sheet and its JSON."""


@dataclass(frozen=True)
class SheetSource:
    """A sheet as the Sheet tab plays it."""

    frames: list[np.ndarray]  # (frame_px, frame_px, 4) uint8, as the sheet holds them
    fps: float
    frame_m: float
    seat: tuple[float, float]  # the seat point as a fraction of the frame, from its top left
    seat_world_m: np.ndarray
    style: SheetLook
    name: str
    recipe: Recipe | None = None  # the resolved recipe the sheet came from, when known
    steps_per_frame: tuple[int, ...] | None = None  # a sheet folder's CFL steps, from settings.toml
    base_steps_per_frame: int = 0
    look_note: str | None = None  # why the look is not the sheet's own recipe's

    @classmethod
    def from_assembly(cls, assembled: AssembledFrames, recipe: Recipe, fps: float) -> "SheetSource":
        return cls(frames=assembled.frames, fps=fps, frame_m=assembled.frame_m, seat=assembled.seat,
                   seat_world_m=seat_point(recipe), style=sheet_look(recipe), name=recipe.output.name,
                   recipe=recipe)

    @classmethod
    def from_folder(cls, folder: Path) -> "SheetSource":
        """The one sheet in `folder` (a `<name>.json` with its `<name>.png`); raises SheetFolderError."""
        json_path = find_sheet(folder)
        try:
            info = json.loads(json_path.read_text(encoding="utf-8"))
            missing = [key for key in SHEET_KEYS if key not in info]
            if missing:
                raise SheetFolderError(f"{json_path} is not a sheet's JSON (no {', '.join(missing)})")
            with Image.open(json_path.with_suffix(".png")) as image:
                pixels = np.asarray(image.convert("RGBA"))
            frames = cut_frames(pixels, int(info["frames"]), int(info["columns"]), int(info["frame_px"]))
            fps, frame_m = float(info["fps"]), float(info["frame_m"])
            seat = (float(info["seat"][0]), float(info["seat"][1]))
        except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
            raise SheetFolderError(f"cannot read the sheet {json_path.with_suffix('.png')}: {error}") from None
        recipe, note, steps, base = _folder_recipe(folder)
        if recipe is not None and recipe.output.channels == info["channels"]:
            style = sheet_look(recipe)
        else:
            style = SheetLook(look=LookSettings(), channels=info["channels"], light_dir=RenderSettings().light_dir)
            if recipe is not None:
                note = f"{SETTINGS_FILE} names another channel layout; drawn with the default look"
        return cls(frames=frames, fps=fps, frame_m=frame_m, seat=seat, seat_world_m=np.zeros(3), style=style,
                   name=json_path.stem, recipe=recipe, steps_per_frame=steps, base_steps_per_frame=base,
                   look_note=note)

    def card_rectangle(self, camera: ViewCamera) -> tuple[float, float, float] | None:
        """The card's left, top and side in the camera's pixels (continuous); None when its seat is behind the
        eye."""
        seat = camera.project(self.seat_world_m)
        if seat is None:
            return None
        meters_per_px = camera.pixel * (camera.ahead(self.seat_world_m) if camera.perspective else 1.0)
        side = self.frame_m / meters_per_px
        return seat[0] - self.seat[0] * side, seat[1] - self.seat[1] * side, side

    def card(self, frame: int, background_hex: str) -> Image.Image:
        """One sheet frame composited over the background, at the sheet's own size."""
        return composited_image(self.frames[frame], background_hex, self.style)


def sheet_image(source: SheetSource, card: Image.Image, camera: ViewCamera, background_hex: str) -> np.ndarray:
    """The Sheet tab for `camera`: the background with the card (from `SheetSource.card`) at its place,
    (height, width, 4) uint8 RGBA."""
    width, height = camera.width_px, camera.height_px
    color = sheet_background(background_hex)[0, 0, :3]
    image = Image.new("RGB", (width, height), tuple(int(value) for value in color))
    rectangle = source.card_rectangle(camera)
    if rectangle is not None:
        left, top, side = rectangle
        x0, y0 = max(0, round(left)), max(0, round(top))
        x1, y1 = min(width, round(left + side)), min(height, round(top + side))
        if x1 > x0 and y1 > y0 and side > 0.0:
            size = card.width
            box = tuple(min(max((value - origin) / side * size, 0.0), size) for value, origin in
                        ((x0, left), (y0, top), (x1, left), (y1, top)))  # rounding can reach past the card
            image.paste(card.resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR, box=box), (x0, y0))
    return np.asarray(image.convert("RGBA"))


def sheet_background(background_hex: str) -> np.ndarray:
    """The background as one RGBA8 pixel, (1, 1, 4), in the composite's sRGB."""
    color = to_srgb_bytes(hex_to_linear(background_hex)[None, :])[0]
    return np.array([[[*color[:3], 255]]], dtype=np.uint8)


def card_home(source: SheetSource) -> tuple[tuple, tuple]:
    """Home's framing for a card seated at the origin: its center and half size on the camera plane."""
    side = source.frame_m
    return ((0.5 - source.seat[0]) * side, (source.seat[1] - 0.5) * side), (side / 2, side / 2)


def home_rectangle(view: DomainView, assembled: AssembledFrames | None) -> tuple[tuple, tuple]:
    """Home's framing on the sheet camera's plane: the center and half width and height (meters) of the
    sheet's crop once the run is assembled, else of its whole domain view."""
    if assembled is not None:
        crop = assembled.crop
        center_px = (crop.left + crop.side / 2, crop.top + crop.side / 2)
        half = (crop.side * view.pixel_m / 2, crop.side * view.pixel_m / 2)
    else:
        center_px = (view.width_px / 2, view.height_px / 2)
        half = (view.width_px * view.pixel_m / 2, view.height_px * view.pixel_m / 2)
    return (view.left_m + center_px[0] * view.pixel_m, view.top_m - center_px[1] * view.pixel_m), half


def find_sheet(folder: Path) -> Path:
    """The JSON of the one sheet in `folder`: a `.json` with a `.png` of the same name."""
    if not folder.is_dir():
        raise SheetFolderError(f"{folder} is not a folder")
    sheets = sorted(path for path in folder.glob("*.json") if path.with_suffix(".png").is_file())
    if not sheets:
        raise SheetFolderError(f"{folder} holds no sheet (a <name>.json beside its <name>.png); "
                               "`plume run` writes one")
    if len(sheets) > 1:
        raise SheetFolderError(f"{folder} holds {len(sheets)} sheets ({', '.join(path.stem for path in sheets)}); "
                               "the viewer opens a folder with one")
    return sheets[0]


def cut_frames(sheet: np.ndarray, frames: int, columns: int, frame_px: int) -> list[np.ndarray]:
    """The sheet's frames, rows left to right, top to bottom (`sheet/pack.py`'s layout)."""
    rows = math.ceil(frames / max(columns, 1))
    if columns < 1 or frames < 1 or sheet.shape[0] < rows * frame_px or sheet.shape[1] < columns * frame_px:
        raise SheetFolderError(f"the sheet is {sheet.shape[1]} x {sheet.shape[0]} pixels, too small for "
                               f"{frames} frames of {frame_px} pixels in {columns} columns")
    cut = []
    for index in range(frames):
        row, column = divmod(index, columns)
        cut.append(sheet[row * frame_px:(row + 1) * frame_px, column * frame_px:(column + 1) * frame_px].copy())
    return cut


def _folder_recipe(folder: Path) -> tuple[Recipe | None, str | None, tuple[int, ...] | None, int]:
    """The resolved recipe in the folder's settings.toml, a note when there is none, and its CFL steps."""
    settings = folder / SETTINGS_FILE
    if not settings.is_file():
        return None, f"no {SETTINGS_FILE} beside the sheet; drawn with the default look", None, 0
    try:
        recipe = load_recipe(settings)
        resolved = tomllib.loads(settings.read_text(encoding="utf-8")).get("resolved", {})
    except (RecipeError, OSError, tomllib.TOMLDecodeError) as error:
        return None, f"{SETTINGS_FILE} does not load ({error}); drawn with the default look", None, 0
    steps = resolved.get("steps_per_frame")
    steps = tuple(int(value) for value in steps) if isinstance(steps, list) else None
    return recipe, None, steps, int(recipe.time.substeps)
