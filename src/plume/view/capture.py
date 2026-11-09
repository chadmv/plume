"""Clips and stills (spec V15): the current view written to disk with a `.toml` beside it saying how to see it
again.

A still is the current frame as a PNG; a clip is every kept frame (Volume) or every sheet frame (Sheet)
as an animated PNG, each shown for `1 / fps`. Both are drawn again at full resolution with the current
camera, view, tab, background, slice plane and side (A, B or Split side by side); the guides and the text
over the viewport are not in them. They go to `<out>/view/`, where `<out>` is `--out`, else
`out/<output.name>/` for a recipe, else the sheet folder itself; named `<name>-f<frame>-<counter>.png` and
`<name>-clip-<counter>.png`, the counter one past the largest in the folder for that name.

The `.toml` holds `[view]` (tab, view, background, side, frame or frames, fps, slice), `[camera]` (the
navigation pose, `Navigation.pose_table`) and `[recipe]` (the resolved recipe, when there is one), so a
thread can read exactly what the user saw and the view can be set up again (`read_capture`).
"""

import re
import tomllib
from pathlib import Path

import numpy as np
import tomli_w
from PIL import Image

from plume.sheet.pack import PNG_COMPRESS_LEVEL

VIEW_FOLDER = "view"
CLIP = "clip"


def capture_folder(out: str | None, output_name: str | None, sheet_folder: Path | None) -> Path:
    """Where captures go: `<out>/view`, else `out/<output_name>/view`, else `<sheet_folder>/view`."""
    if out:
        base = Path(out)
    elif output_name is not None:
        base = Path("out") / output_name
    else:
        base = sheet_folder
    return base / VIEW_FOLDER


def next_counter(folder: Path, name: str) -> int:
    """One past the largest counter of this name's stills and clips in `folder` (1 when there are none)."""
    pattern = re.compile(rf"{re.escape(name)}-(?:f\d+|{CLIP})-(\d+)\.png")
    counters = [int(match.group(1)) for path in folder.glob(f"{name}-*.png")
                if (match := pattern.fullmatch(path.name))] if folder.is_dir() else []
    return max(counters, default=0) + 1


def write_still(folder: Path, name: str, frame: int, image: np.ndarray, info: dict) -> Path:
    """Writes the image as `<name>-f<frame>-<counter>.png` and its `.toml`; returns the PNG's path."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}-f{frame:03d}-{next_counter(folder, name):03d}.png"
    Image.fromarray(np.ascontiguousarray(image)).save(path, format="PNG", compress_level=PNG_COMPRESS_LEVEL)
    _write_toml(path, info)
    return path


def write_clip(folder: Path, name: str, images: list[np.ndarray], fps: float, info: dict) -> Path:
    """Writes the images as an animated PNG `<name>-clip-<counter>.png`, each shown 1 / fps, looping, and its
    `.toml`; returns the PNG's path."""
    if not images:
        raise ValueError("a clip needs at least one image")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}-{CLIP}-{next_counter(folder, name):03d}.png"
    pictures = [Image.fromarray(np.ascontiguousarray(image)) for image in images]
    pictures[0].save(path, format="PNG", save_all=True, append_images=pictures[1:], duration=1000.0 / fps, loop=0,
                     compress_level=PNG_COMPRESS_LEVEL)
    _write_toml(path, info)
    return path


def read_capture(png_path: Path) -> dict:
    """The `.toml` beside a still or clip."""
    return tomllib.loads(png_path.with_suffix(".toml").read_text(encoding="utf-8"))


def _write_toml(png_path: Path, info: dict) -> None:
    png_path.with_suffix(".toml").write_text(tomli_w.dumps(info), encoding="utf-8", newline="\n")
