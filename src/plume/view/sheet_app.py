"""The sheet-only window (`plume view OUT_DIR`, spec V9): a finished sheet played on its card, with no
recipe, no simulation and no GPU.

The Sheet tab alone: the card facing the camera over the chosen background, the camera's navigation (the
card's seat at the origin; Home frames the card at the sheet's own camera angles when its `settings.toml`
names them), the transport at the sheet's fps, the numbers strip measured from the sheet's frames, and
stills and clips into the folder's `view/` (or `--out`'s).
"""

import time
from pathlib import Path

import numpy as np
from imgui_bundle import hello_imgui, imgui

from plume import tool_label
from plume.recipe.schema import LookSettings
from plume.recipe.serialize import recipe_table
from plume.sheet.sheet_json import source_path
from plume.view.camera_input import CameraInput
from plume.view.capture import capture_folder, write_clip, write_still
from plume.view.navigation import Navigation
from plume.view.numbers_strip import STRIP_PX, draw_strip, strip_data
from plume.view.sheet_player import SheetSource, card_home, sheet_image
from plume.view.transport import Transport
from plume.view.window_parts import (BACKGROUND_NAMES, NOTE_COLOR, Textures, background_hex, draw_banners,
                                     draw_text_lines, start_plotting, stop_plotting)

WINDOW_SIZE = (1200, 900)
BOTTOM_BAR_PX = 64 + STRIP_PX + 8
TAB = "sheet"


def run_sheet_viewer(folder: Path, source: SheetSource, out: str | None = None) -> None:
    """Opens the window on a sheet folder and runs it until it is closed."""
    app = SheetApp(folder, source, out)
    hello_imgui.run(app.runner_params())


class SheetApp:
    """The sheet-only window's state between updates."""

    def __init__(self, folder: Path, source: SheetSource, out: str | None = None):
        self.folder = folder
        self.source = source
        self.out = out
        side = source.frame_m
        self.nav = Navigation((-side / 2, -side / 2, -side / 2), (side, side, side))
        self.nav_needs_home = True
        self.transport = Transport()
        self.input = CameraInput()
        self.background_index = 0
        self.textures = Textures(panes=1)
        self.drawn_key = None
        self.card = None  # (key, composited card)
        frames = len(source.frames)
        self.strip = strip_data(frames, source.frames, source.fps, None, source.steps_per_frame,
                                source.base_steps_per_frame)
        self.capture_notice: str | None = None
        self.last_update_s = time.perf_counter()

    @property
    def look(self) -> LookSettings:
        return self.source.style.look

    def runner_params(self) -> hello_imgui.RunnerParams:
        params = hello_imgui.RunnerParams()
        params.app_window_params.window_title = f"plume view - {self.folder.name}"
        params.app_window_params.window_geometry.size = WINDOW_SIZE
        params.imgui_window_params.default_imgui_window_type = (
            hello_imgui.DefaultImGuiWindowType.provide_full_screen_window)
        params.fps_idling.enable_idling = False
        params.ini_disable = True
        params.callbacks.post_init = self._post_init
        params.callbacks.show_gui = self.gui
        params.callbacks.before_exit = self._before_exit
        return params

    def gui(self) -> None:
        now = time.perf_counter()
        dt = min(now - self.last_update_s, 0.1)
        self.last_update_s = now
        kept = list(range(len(self.source.frames)))
        self.transport.advance(dt, kept, self.source.fps, live=False)
        self._top_bar()
        size = imgui.get_content_region_avail()
        width, height = int(size.x), int(size.y) - BOTTOM_BAR_PX
        if width >= 8 and height >= 8:
            self._viewport(now, dt, width, height)
        frames = len(self.source.frames)
        self.transport.draw(frames, kept, 1.0, f"sheet {frames} frames at {self.source.fps:g} fps", frames - 1)
        moved = draw_strip(self.strip, self.transport.playhead, imgui.get_content_region_avail().x)
        if moved is not None:
            self.transport.scrub_to(moved, kept)

    def _top_bar(self) -> None:
        imgui.text(str(self.folder))
        imgui.same_line()
        imgui.text_disabled(f"| Sheet: {self.source.name}")
        imgui.same_line()
        if imgui.button(f"Background: {BACKGROUND_NAMES[self.background_index]} (B)"):
            self.background_index = (self.background_index + 1) % len(BACKGROUND_NAMES)
        imgui.same_line()
        if imgui.button("Persp (P)" if self.nav.perspective else "Ortho (P)"):
            self.nav.toggle_perspective()
        imgui.same_line()
        if imgui.button("Still (F12)"):
            self._save_still()
        imgui.same_line()
        if imgui.button("Save clip"):
            self._save_clip()
        if self.capture_notice:
            imgui.same_line()
            imgui.text_disabled(self.capture_notice)
        imgui.same_line()
        imgui.text_disabled(f"| {tool_label()}")

    def _viewport(self, now: float, dt: float, width: int, height: int) -> None:
        self.nav.set_viewport(width, height)
        if self.nav_needs_home:
            self._home()
            self.nav_needs_home = False
        origin = imgui.get_cursor_screen_pos()
        frame = self.transport.playhead
        key = (frame, self.nav.pose(), self.background_index)
        if key != self.drawn_key:
            self.textures.upload(0, self._render(frame))
            self.drawn_key = key
        self.textures.image(0, width, height)
        hovered = imgui.is_item_hovered()
        self.input.update(self.nav, now, dt, hovered, lambda: None)
        io = imgui.get_io()
        if not self.input.free_look and not io.want_text_input:
            self._keys(io)
        draw_list = imgui.get_window_draw_list()
        draw_list.push_clip_rect(origin, imgui.ImVec2(origin.x + width, origin.y + height), True)
        lines = [f"{'Persp' if self.nav.perspective else 'Ortho'}   frame {frame} / {len(self.source.frames) - 1}   "
                 f"t {(frame + 1) / self.source.fps:.3f} s   frame_m {self.source.frame_m:.3f} m"]
        y = draw_text_lines(draw_list, origin, lines)
        if self.source.look_note:
            draw_banners(draw_list, origin, width, y, [(NOTE_COLOR, self.source.look_note)])
        draw_list.pop_clip_rect()

    def _render(self, frame: int) -> np.ndarray:
        background = background_hex(self.look, self.background_index)
        key = (frame, background)
        if self.card is None or self.card[0] != key:
            self.card = (key, self.source.card(frame, background))
        return sheet_image(self.source, self.card[1], self.nav.view_camera(), background)

    def _keys(self, io) -> None:
        pressed = imgui.is_key_pressed
        self.transport.keys(io, list(range(len(self.source.frames))))
        if pressed(imgui.Key.b, False):
            self.background_index = (self.background_index + 1) % len(BACKGROUND_NAMES)
        if pressed(imgui.Key.p, False):
            self.nav.toggle_perspective()
        if pressed(imgui.Key.home, False):
            self._home()
        if pressed(imgui.Key.f, False):
            self.nav.frame(self.nav.domain_center, self.source.frame_m * 0.75)
        if pressed(imgui.Key.f12, False):
            self._save_still()

    def _home(self) -> None:
        """The card square on, at the sheet camera's angles when its recipe is known."""
        camera = self.source.recipe.camera if self.source.recipe is not None else None
        center, half = card_home(self.source)
        self.nav.home(camera.elevation_deg if camera else 0.0, camera.azimuth_deg if camera else 0.0, center, half)

    def _save_still(self) -> None:
        frame = self.transport.playhead
        path = write_still(self._folder(), self.source.name, frame, self._render(frame), self._info(frame=frame))
        self.capture_notice = f"saved {path}"

    def _save_clip(self) -> None:
        frames = list(range(len(self.source.frames)))
        images = [self._render(frame) for frame in frames]
        path = write_clip(self._folder(), self.source.name, images, self.source.fps, self._info(frames=frames))
        self.capture_notice = f"saved {path}"

    def _folder(self) -> Path:
        return capture_folder(self.out, None, self.folder)

    def _info(self, frame: int | None = None, frames: list[int] | None = None) -> dict:
        view = {"sheet": source_path(self.folder), "tab": TAB, "background": BACKGROUND_NAMES[self.background_index],
                "background_hex": background_hex(self.look, self.background_index), "side": "A",
                "fps": self.source.fps}
        if frame is not None:
            view["frame"] = frame
        if frames is not None:
            view["frames"] = frames
        info = {"view": view, "camera": self.nav.pose_table()}
        if self.source.recipe is not None:
            info["recipe"] = recipe_table(self.source.recipe)
        return info

    def _post_init(self) -> None:
        io = imgui.get_io()
        io.config_flags &= ~imgui.ConfigFlags_.nav_enable_keyboard
        start_plotting()

    def _before_exit(self) -> None:
        self.textures.delete()
        stop_plotting()
