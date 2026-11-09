"""The viewer window on a recipe: input, layout and the panels, around the session, navigation and viewport.

One window update does, in order: follow the recipe on disk and simulate one frame of a live run
(`Session.update`), move the playhead, apply the camera input, redraw the viewport if anything it shows
changed, and draw the bars, the numbers strip and the editing panel. Every Warp launch happens here, on the
window's thread.

Two tabs over one viewport (`Tab`): **Volume** draws the kept fields from the camera, with the slice plane
(`L`) over them; **Sheet** plays the assembled sheet on a card facing the camera (`sheet_player.py`). The
viewport shows A (the current run), B (the run before, `C`), or both side by side with one camera (Split).
The right panel (`panel.py`) holds Save, Revert, Compare and every recipe key. Stills (`F12`) and clips
(`capture.py`) draw the view again at full size and write it with a `.toml` beside it.
"""

import math
import time
from pathlib import Path

import numpy as np
from imgui_bundle import hello_imgui, imgui

from plume import tool_label
from plume.recipe.schema import SHADE_LAYOUT
from plume.recipe.serialize import recipe_table
from plume.sheet.sheet_json import source_path
from plume.view.camera_input import CameraInput
from plume.view.capture import capture_folder, write_clip, write_still
from plume.view.guides import (BOX, EMITTER, LIGHT, LIGHT_GRAB_PX, TICK, dashes, guide_segments,
                               light_arrow_span, light_dir_in_camera, on_screen, turn_light)
from plume.view.navigation import Navigation, ViewCamera, smoke_bounds
from plume.view.numbers_strip import STRIP_PX, StripData, draw_strip, strip_data
from plume.view.panel import EditingPanel
from plume.view.session import Session, Snapshot
from plume.view.sheet_player import SheetSource, home_rectangle, sheet_background, sheet_image
from plume.view.slice_plane import AXIS_NAMES, FIELDS, UNITS, VELOCITY_FIELDS, SliceDrawer, SlicePlane, ramp_colors
from plume.view.transport import Transport
from plume.view.viewport import HEAT_VIEW, LOOK, SHADE_VIEW, THICKNESS_VIEW
from plume.view.window_parts import (BACKGROUND_NAMES, ERROR_COLOR, NOTE_COLOR, Textures, background_hex,
                                     draw_banners, draw_text_lines, start_plotting, stop_plotting)

WINDOW_SIZE = (1600, 900)
MOVING_S = 0.25  # the viewport draws at half resolution until the camera has been still this long
# and while a live run is still landing frames (so the run finishes sooner; it goes sharp once done)
TRIM_SHOWN_S = 1.5
BOTTOM_BAR_PX = 64 + STRIP_PX + 8
GUIDE_COLORS = {BOX: (0.85, 0.85, 0.85, 0.55), TICK: (0.85, 0.85, 0.85, 0.55), EMITTER: (1.0, 0.6, 0.2, 0.8),
                LIGHT: (1.0, 0.9, 0.3, 0.9)}
PANEL_PX = 430
VOLUME, SHEET = "volume", "sheet"
VIEW_NAMES = {LOOK: "look", HEAT_VIEW: "heat", THICKNESS_VIEW: "thickness", SHADE_VIEW: "shade"}
LEGEND_PX = (180, 12)
LEGEND_STEPS = 32


def run_viewer(session: Session, out: str | None = None) -> None:
    """Opens the window and runs it until it is closed; captures go under `out` (`--out`) when given."""
    app = ViewerApp(session, out)
    hello_imgui.run(app.runner_params())


class ViewerApp:
    """The window's state between updates."""

    def __init__(self, session: Session, out: str | None = None):
        self.session = session
        self.out = out
        self.tab = VOLUME
        self.view = LOOK
        self.background_index = 0
        self.show_guides = True
        self.transport = Transport()
        self.nav: Navigation | None = None
        self.plane: SlicePlane | None = None
        self.nav_needs_home = True
        self.domain = None
        self.run_seen = None
        self.simulation_seen = None
        self.panel = EditingPanel(session)
        self.light_preview: np.ndarray | None = None  # the light direction while its arrow is dragged
        self.pane_origin = None  # the viewport's top left on screen, for the light arrow's grab
        self.input = CameraInput()
        self.drawn_keys: list = [None, None]
        self.redraw_ms = 0.0
        self.drawn_half = False
        self.textures = Textures()
        self.slices = [None, None]  # each pane's SliceDrawer, made on first use (Warp arrays)
        self.slice_drawn = [False, False]  # whether each pane's last image holds a slice (its legend shows)
        self.sheets: dict[tuple, SheetSource] = {}  # by (run serial, viewport serial): a look edit makes a new one
        self.cards: list = [None, None]  # each pane's (key, composited card)
        self.strip: tuple | None = None  # (key, StripData)
        self.capture_notice: str | None = None
        self.last_update_s = time.perf_counter()

    def runner_params(self) -> hello_imgui.RunnerParams:
        params = hello_imgui.RunnerParams()
        params.app_window_params.window_title = f"plume view - {self.session.recipe_path.name}"
        params.app_window_params.window_geometry.size = WINDOW_SIZE
        params.imgui_window_params.default_imgui_window_type = (
            hello_imgui.DefaultImGuiWindowType.provide_full_screen_window)
        params.fps_idling.enable_idling = False
        params.ini_disable = True  # no layout file written beside the recipe
        params.callbacks.post_init = self._post_init
        params.callbacks.show_gui = self.gui
        params.callbacks.before_exit = self._before_exit
        return params

    # -- one update -------------------------------------------------------------------------------------------

    def gui(self) -> None:
        now = time.perf_counter()
        dt = min(now - self.last_update_s, 0.1)
        self.last_update_s = now
        self.session.update(now)
        self._follow_run()
        run = self.session.run
        self.transport.advance(dt, self._kept(), self.session.derived.fps,
                               live=self.tab == VOLUME and not (run.done or run.stopped))
        self._top_bar()
        available = imgui.get_content_region_avail()
        imgui.begin_child("view_area", imgui.ImVec2(max(available.x - PANEL_PX, 8), 0))
        self._viewport(now, dt)
        self._bottom_bar()
        imgui.end_child()
        imgui.same_line()
        imgui.begin_child("panel", imgui.ImVec2(0, 0), imgui.ChildFlags_.borders)
        self.panel.draw()
        imgui.end_child()

    def _follow_run(self) -> None:
        session = self.session
        domain = (session.derived.domain_min_m, session.derived.size_m)
        if domain != self.domain:
            self.domain = domain
            self.nav = Navigation(*domain)
            axis = self.plane.axis if self.plane is not None else None
            self.plane = SlicePlane(np.array(domain[0]), np.array(domain[1]), axis=axis,
                                    field_name=self.plane.field_name if self.plane is not None else FIELDS[0])
            self.nav_needs_home = True
        if session.run is not self.run_seen:
            self.run_seen = session.run
            self.drawn_keys = [None, None]
            if session.run.simulation_serial != self.simulation_seen:  # a re-capture keeps the playhead
                self.simulation_seen = session.run.simulation_serial
                self.transport.restart()
        if session.compare is None:
            self.panel.showing_b = False
        on_screen = {_sheet_key(snapshot) for snapshot in (session.current, session.compare) if snapshot}
        self.sheets = {key: sheet for key, sheet in self.sheets.items() if key in on_screen}

    def _kept(self) -> list[int]:
        """The frames the playhead steps over: the sheet's frames in the Sheet tab, else the kept frames."""
        sheet = self._sheet(self.session.current)
        if self.tab == SHEET and sheet is not None:
            return list(range(len(sheet.frames)))
        return self.session.run.cache.kept_frames()

    def _sheet(self, snapshot: Snapshot) -> SheetSource | None:
        """The run's assembled sheet as the Sheet tab plays it; None until it is assembled."""
        run = snapshot.run
        if run.assembled is None:
            return None
        key = _sheet_key(snapshot)
        if key not in self.sheets:
            self.sheets[key] = SheetSource.from_assembly(run.assembled, snapshot.recipe, run.derived.fps)
        return self.sheets[key]

    # -- the bars -----------------------------------------------------------------------------------------

    def _top_bar(self) -> None:
        session = self.session
        imgui.text(str(session.recipe_path))
        imgui.same_line()
        imgui.text_disabled("|")
        for tab, name in ((VOLUME, "Volume"), (SHEET, "Sheet")):
            imgui.same_line()
            if imgui.radio_button(f"{name}##tab", self.tab == tab):
                self.tab = tab
        imgui.same_line()
        imgui.text_disabled("(Tab) |")
        layout_name = "Shade" if session.recipe.output.channels == SHADE_LAYOUT else "Normal"
        imgui.begin_disabled(self.tab != VOLUME)
        for view, name in ((LOOK, "Look"), (HEAT_VIEW, "Heat"), (THICKNESS_VIEW, "Thickness"),
                           (SHADE_VIEW, layout_name)):
            imgui.same_line()
            if imgui.radio_button(f"{name} ({view + 1})", self.view == view):
                self.view = view
        imgui.end_disabled()
        imgui.same_line()
        _, self.show_guides = imgui.checkbox("Guides (G)", self.show_guides)
        imgui.same_line()
        if imgui.radio_button("Full", not session.preview):
            session.set_preview(False)
        imgui.same_line()
        if imgui.radio_button("Preview", session.preview):
            session.set_preview(True)
        imgui.same_line()
        if imgui.button(f"Background: {BACKGROUND_NAMES[self.background_index]} (B)"):
            self.background_index = (self.background_index + 1) % len(BACKGROUND_NAMES)
        imgui.same_line()
        if imgui.button("Persp (P)" if self.nav.perspective else "Ortho (P)"):
            self.nav.toggle_perspective()
        self._slice_controls()
        imgui.same_line()
        imgui.text_disabled("|")
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
        imgui.text_disabled(f"| {session.device} | {tool_label()}")

    def _slice_controls(self) -> None:
        plane = self.plane
        imgui.begin_disabled(self.tab != VOLUME)
        axis = "off" if plane.axis is None else AXIS_NAMES[plane.axis]
        if imgui.button(f"Slice: {axis} (L)"):
            plane.cycle()
        imgui.same_line()
        imgui.set_next_item_width(110)
        if imgui.begin_combo("##slice_field", plane.field_name):
            has_velocity = self.session.run.cache.has_velocity
            for name in FIELDS:
                imgui.begin_disabled(name in VELOCITY_FIELDS and not has_velocity)
                if imgui.selectable(name, name == plane.field_name)[0]:
                    plane.field_name = name
                imgui.end_disabled()
            imgui.end_combo()
        if imgui.is_item_hovered() and not self.session.run.cache.has_velocity:
            imgui.set_tooltip("speed and swirl need the frames' velocity, which this run's frame cache dropped")
        imgui.end_disabled()

    def _bottom_bar(self) -> None:
        session = self.session
        run = session.run
        kept = self._kept()
        landed = run.landed
        if self.tab == SHEET:
            sheet = self._sheet(session.current)
            status = "sheet ready" if sheet is not None else "sheet assembles when the run is done"
            frames, progress, limit = run.frames, 1.0 if sheet is not None else 0.0, run.frames - 1
        else:
            if run.recaptured:
                status = "re-capture " + ("stopped" if run.stopped else "running" if run.capturing else "done")
            else:
                status = "run " + ("done" if run.done else ("stopped" if run.stopped else "running"))
            frames, progress, limit = run.frames, landed / run.frames, landed - 1
            status = f"{status} {landed}/{run.frames}"
        self.transport.draw(frames, kept, progress, status, limit)
        moved = draw_strip(self._strip_data(), self.transport.playhead, imgui.get_content_region_avail().x)
        if moved is not None:
            self.transport.scrub_to(min(moved, max(limit, 0)), kept)

    def _strip_data(self) -> StripData:
        run = self.session.run
        key = (run.serial, run.assembled is not None, len(run.edges), run.done)
        if self.strip is None or self.strip[0] != key:
            steps = run.steps
            data = strip_data(run.frames, run.assembled.frames if run.assembled else None, run.derived.fps,
                              run.edges, steps.steps_per_frame if steps else None,
                              steps.base_steps_per_frame if steps else 0)
            self.strip = (key, data)
        return self.strip[1]

    # -- the viewport ---------------------------------------------------------------------------------------

    def _shown(self) -> list[Snapshot]:
        """What the viewport shows, left to right: A, B, or both (Split)."""
        session = self.session
        if session.compare is not None and self.panel.split:
            return [session.current, session.compare]
        if session.compare is not None and self.panel.showing_b:
            return [session.compare]
        return [session.current]

    def _viewport(self, now: float, dt: float) -> None:
        size = imgui.get_content_region_avail()
        width, height = int(size.x), int(size.y) - BOTTOM_BAR_PX
        shown = self._shown()
        pane_width = width // len(shown)
        if pane_width < 8 or height < 8:
            return
        self.nav.set_viewport(pane_width, height)
        if self.nav_needs_home:
            self._home()
            self.nav_needs_home = False
        origin = imgui.get_cursor_screen_pos()
        self.pane_origin = origin
        shown_camera = self.nav.view_camera()  # the pose the image shows; the input below moves the next one
        hovered = False
        for pane, snapshot in enumerate(shown):
            self._redraw(pane, snapshot, now)
            if pane:
                imgui.same_line(0, 0)
            self.textures.image(pane, pane_width, height)
            hovered = hovered or imgui.is_item_hovered()
        a_shown = shown[0] is self.session.current
        self._camera_input(now, dt, hovered, shown_camera, shown_camera if a_shown else None)
        draw_list = imgui.get_window_draw_list()
        for pane, snapshot in enumerate(shown):
            pane_origin = imgui.ImVec2(origin.x + pane * pane_width, origin.y)
            draw_list.push_clip_rect(pane_origin, imgui.ImVec2(pane_origin.x + pane_width, origin.y + height), True)
            if self.show_guides:
                light = self.light_preview if snapshot is self.session.current else None
                self._draw_guides(draw_list, pane_origin, shown_camera, snapshot, light)
            if self.session.compare is not None:
                self._draw_tag(draw_list, pane_origin, pane_width, "A" if snapshot is self.session.current else "B")
            if self._slice_on() and self.slice_drawn[pane]:
                self._draw_legend(draw_list, pane_origin, pane_width, height, pane)
            draw_list.pop_clip_rect()
        draw_list.push_clip_rect(origin, imgui.ImVec2(origin.x + width, origin.y + height), True)
        self._draw_overlay(draw_list, origin, width, now)
        draw_list.pop_clip_rect()

    def _slice_on(self) -> bool:
        return self.tab == VOLUME and self.plane.axis is not None

    def _redraw(self, pane: int, snapshot: Snapshot, now: float) -> None:
        run = snapshot.run
        frame = self._frame_of(snapshot)
        if frame is None:
            if self.tab == SHEET and self.drawn_keys[pane] != (SHEET, None, self.background_index):
                color = sheet_background(background_hex(snapshot.recipe.look, self.background_index))
                self.textures.upload(pane, color)  # the background until the sheet is assembled
                self.drawn_keys[pane] = (SHEET, None, self.background_index)
            return
        half = self.tab == VOLUME and (now - self.input.moved_s < MOVING_S or not (run.done or run.stopped))
        plane = self.plane
        slice_key = (plane.axis, plane.coordinate_m if plane.axis is not None else None, plane.field_name)
        key = (self.tab, run.serial, snapshot.viewport.serial, frame, self.nav.pose(), self.view,
               self.background_index, half, run.heat_divisor, run.shade_divisor,
               slice_key if self._slice_on() else None, run.assembled is not None)
        if key == self.drawn_keys[pane]:
            return
        started = time.perf_counter()
        camera = self.nav.view_camera(max(1, self.nav.width_px // 2), max(1, self.nav.height_px // 2)) if half \
            else self.nav.view_camera()
        image = self._render(pane, snapshot, frame, camera)
        self.textures.upload(pane, image)
        self.redraw_ms = (time.perf_counter() - started) * 1000.0
        self.drawn_half = half
        self.drawn_keys[pane] = key

    def _frame_of(self, snapshot: Snapshot) -> int | None:
        """The frame a pane shows at the playhead: the sheet frame in the Sheet tab, else the nearest kept."""
        if self.tab == SHEET:
            sheet = self._sheet(snapshot)
            if sheet is None:
                return None
            return min(self.transport.playhead, len(sheet.frames) - 1)
        return snapshot.run.cache.nearest_kept(self.transport.playhead)

    def _render(self, pane: int, snapshot: Snapshot, frame: int, camera: ViewCamera) -> np.ndarray:
        """One pane's image of a frame for a camera: the Sheet tab's card, or the volume with the slice."""
        background = background_hex(snapshot.recipe.look, self.background_index)
        if self.tab == SHEET:
            sheet = self._sheet(snapshot)
            key = (_sheet_key(snapshot), frame, background)
            if self.cards[pane] is None or self.cards[pane][0] != key:
                self.cards[pane] = (key, sheet.card(frame, background))
            return sheet_image(sheet, self.cards[pane][1], camera, background)
        overlay = None
        self.slice_drawn[pane] = False
        if self._slice_on():
            if self.slices[pane] is None:
                self.slices[pane] = SliceDrawer(self.session.device)
            drawer = self.slices[pane]
            if drawer.prepare(snapshot.run, frame, self.plane.field_name):
                self.slice_drawn[pane] = True

                def overlay(image, drawn_camera):
                    drawer.overlay(image, drawn_camera, snapshot.run, self.plane)
        return snapshot.viewport.draw(snapshot.run, frame, camera, self.view, background, overlay)

    def _camera_input(self, now: float, dt: float, hovered: bool, camera: ViewCamera,
                      a_camera: ViewCamera | None) -> None:
        """The camera's input, plus this window's own left drags: the light arrow's tip (`a_camera` is the
        camera A's pane was drawn with, None when A is not on screen) and the slice plane."""
        io = imgui.get_io()
        left = imgui.MouseButton_.left
        moving = self.input
        if hovered and moving.idle and not io.key_alt and imgui.is_mouse_clicked(left):
            if a_camera is not None and self.show_guides and self.tab == VOLUME and self._near_light_tip(a_camera):
                moving.drag = "light"
                self.light_preview = self.session.viewport.toward_light_world.copy()
            elif self._slice_on():
                moving.drag = "slice"
        delta = io.mouse_delta
        if moving.drag == "light":
            if not imgui.is_mouse_down(left):
                self._release_light()
            elif (delta.x or delta.y) and a_camera is not None:
                self.light_preview = turn_light(self.light_preview, delta.x, delta.y, a_camera,
                                                self.session.derived)
        elif moving.drag == "slice":
            if not imgui.is_mouse_down(left) or not self._slice_on():
                moving.drag = None
            elif delta.x or delta.y:
                self.plane.drag(delta.x, delta.y, camera)
        moving.update(self.nav, now, dt, hovered, self._release_hit)
        if not moving.free_look and not io.want_text_input:
            self._keys(io)

    def _keys(self, io) -> None:
        pressed = imgui.is_key_pressed
        self.transport.keys(io, self._kept())
        if pressed(imgui.Key.tab, False):
            self.tab = SHEET if self.tab == VOLUME else VOLUME
        for key, view in ((imgui.Key._1, LOOK), (imgui.Key._2, HEAT_VIEW), (imgui.Key._3, THICKNESS_VIEW),
                          (imgui.Key._4, SHADE_VIEW)):
            if pressed(key, False):
                self.view = view
        if pressed(imgui.Key.g, False):
            self.show_guides = not self.show_guides
        if pressed(imgui.Key.b, False):
            self.background_index = (self.background_index + 1) % len(BACKGROUND_NAMES)
        if pressed(imgui.Key.p, False):
            self.nav.toggle_perspective()
        if pressed(imgui.Key.l, False) and self.tab == VOLUME:
            self.plane.cycle()
        if pressed(imgui.Key.home, False):
            self._home()
        if pressed(imgui.Key.f, False):
            self._frame(whole_domain=io.key_shift)
        if pressed(imgui.Key.f12, False):
            self._save_still()
        if pressed(imgui.Key.c, False) and not io.key_ctrl and self.session.compare is not None:
            self.panel.showing_b = not self.panel.showing_b
        if io.key_ctrl and pressed(imgui.Key.s, False):
            self.session.save()

    def _home(self) -> None:
        """The sheet camera, framing the sheet's crop once the run is assembled, else its domain view."""
        run = self.session.run
        center, half = home_rectangle(run.view, run.assembled)
        camera = self.session.recipe.camera
        self.nav.home(camera.elevation_deg, camera.azimuth_deg, center, half)

    def _frame(self, whole_domain: bool) -> None:
        session = self.session
        nav = self.nav
        bounds = None
        frame = session.run.cache.nearest_kept(self.transport.playhead)
        if not whole_domain and frame is not None:
            smoke = session.viewport.smoke_on_host(session.run, frame)
            bounds = smoke_bounds(smoke, session.derived.domain_min_m, session.recipe.domain.cell_m,
                                  session.viewport.visible_density())
        if bounds is None:
            bounds = (nav.domain_center, float(np.linalg.norm(nav.domain_size)) / 2)
        nav.frame(*bounds)

    def _release_hit(self):
        session = self.session
        frame = session.run.cache.nearest_kept(self.transport.playhead)
        if frame is None:
            return None
        return session.viewport.center_hit(session.run, frame, self.nav.view_camera())

    # -- stills and clips -----------------------------------------------------------------------------------

    def _save_still(self) -> None:
        shown = self._shown()
        frames = [self._frame_of(snapshot) for snapshot in shown]
        if any(frame is None for frame in frames):
            self.capture_notice = "nothing to save yet"
            return
        camera = self.nav.view_camera()
        image = np.concatenate([self._render(pane, snapshot, frame, camera)
                                for pane, (snapshot, frame) in enumerate(zip(shown, frames, strict=True))], axis=1)
        path = write_still(self._capture_folder(), self._capture_name(), frames[0], image,
                           self._capture_info(frame=frames[0]))
        self.drawn_keys = [None, None]  # the panes' scratch was drawn over at full size
        self.capture_notice = f"saved {path}"

    def _save_clip(self) -> None:
        shown = self._shown()
        run = self.session.run
        if self.tab == SHEET:
            sheet = self._sheet(self.session.current)
            frames = list(range(len(sheet.frames))) if sheet is not None else []
        else:
            frames = run.cache.kept_frames() if (run.done or run.stopped) else []
        if not frames or any(self._frame_of(snapshot) is None for snapshot in shown):
            self.capture_notice = "a clip needs a finished run" + (" and its sheet" if self.tab == SHEET else "")
            return
        camera = self.nav.view_camera()
        images = []
        for frame in frames:
            panes = []
            for pane, snapshot in enumerate(shown):
                shown_frame = (min(frame, len(self._sheet(snapshot).frames) - 1) if self.tab == SHEET
                               else snapshot.run.cache.nearest_kept(frame))
                panes.append(self._render(pane, snapshot, shown_frame, camera))
            images.append(np.concatenate(panes, axis=1))
        fps = self.session.derived.fps
        path = write_clip(self._capture_folder(), self._capture_name(), images, fps, self._capture_info(frames=frames))
        self.drawn_keys = [None, None]
        self.capture_notice = f"saved {path}"

    def _capture_folder(self) -> Path:
        return capture_folder(self.out, self.session.recipe.output.name, None)

    def _capture_name(self) -> str:
        return self.session.recipe.output.name

    def _capture_info(self, frame: int | None = None, frames: list[int] | None = None) -> dict:
        session = self.session
        shown = self._shown()
        side = "split" if len(shown) == 2 else ("B" if shown[0] is not session.current else "A")
        view = {"recipe": source_path(session.recipe_path), "tab": self.tab, "view": VIEW_NAMES[self.view],
                "background": BACKGROUND_NAMES[self.background_index],
                "background_hex": background_hex(session.recipe.look, self.background_index), "side": side,
                "fps": session.derived.fps, "preview": session.preview}
        if frame is not None:
            view["frame"] = frame
        if frames is not None:
            view["frames"] = frames
        if self._slice_on():
            view["slice"] = {"axis": AXIS_NAMES[self.plane.axis], "position_m": self.plane.coordinate_m,
                             "field": self.plane.field_name}
        info = {"view": view, "camera": self.nav.pose_table(), "recipe": recipe_table(session.recipe)}
        if side != "A":
            info["recipe_b"] = recipe_table(session.compare.recipe)
        return info

    # -- drawing over the viewport --------------------------------------------------------------------------

    def _draw_guides(self, draw_list, origin, camera, snapshot: Snapshot, light: np.ndarray | None) -> None:
        light = snapshot.viewport.toward_light_world if light is None else light
        segments = guide_segments(snapshot.recipe, snapshot.run.derived, self.transport.playhead, light)
        for segment in segments:
            ends = on_screen(camera, segment)
            if ends is None:
                continue
            color = imgui.get_color_u32(imgui.ImVec4(*GUIDE_COLORS[segment.kind]))
            pieces = dashes(*ends) if segment.dashed else [ends]
            for start, end in pieces:
                draw_list.add_line(imgui.ImVec2(origin.x + start[0], origin.y + start[1]),
                                   imgui.ImVec2(origin.x + end[0], origin.y + end[1]), color, 1.5)

    def _draw_legend(self, draw_list, origin, width: int, height: int, pane: int) -> None:
        """The slice's field, range and ramp in the pane's bottom right (each pane its own range)."""
        drawer = self.slices[pane]
        if drawer is None:
            return
        low, high = drawer.range
        unit = UNITS[self.plane.field_name]
        bar_width, bar_height = LEGEND_PX
        x = origin.x + width - bar_width - 12
        y = origin.y + height - bar_height - 30
        colors = ramp_colors(LEGEND_STEPS)
        step = bar_width / LEGEND_STEPS
        for index, color in enumerate(colors):
            draw_list.add_rect_filled(imgui.ImVec2(x + index * step, y),
                                      imgui.ImVec2(x + (index + 1) * step + 0.5, y + bar_height),
                                      imgui.get_color_u32(imgui.ImVec4(*color, 1.0)))
        white = imgui.get_color_u32(imgui.ImVec4(1.0, 1.0, 1.0, 0.95))
        title = (f"{self.plane.field_name} on {AXIS_NAMES[self.plane.axis]} = {self.plane.coordinate_m:.3f} m")
        draw_list.add_text(imgui.ImVec2(x, y - 18), white, title)
        draw_list.add_text(imgui.ImVec2(x, y + bar_height + 2), white, f"{low:.4g}")
        high_text = f"{high:.4g} {unit}".strip()
        draw_list.add_text(imgui.ImVec2(x + bar_width - imgui.calc_text_size(high_text).x, y + bar_height + 2),
                           white, high_text)

    def _draw_overlay(self, draw_list, origin, width: int, now: float) -> None:
        session = self.session
        run = session.run
        derived = session.derived
        frame = self._frame_of(session.current)
        lines = [
            f"{'Persp' if self.nav.perspective else 'Ortho'}   {self.tab}   frame "
            f"{frame if frame is not None else '-'} / {run.frames - 1}   t {derived.frame_time_s(frame or 0):.3f} s",
            f"redraw {self.redraw_ms:.1f} ms{' (half)' if self.drawn_half else ''}   "
            f"run {session.run_seconds:.2f} s",
        ]
        if now - self.input.trim_changed_s < TRIM_SHOWN_S:
            lines.append(f"fly speed x{self.nav.fly_trim:.2f}")
        y = draw_text_lines(draw_list, origin, lines)
        banners = []
        if session.error:
            banners.append((ERROR_COLOR, session.error))
        if session.kept_edits_note:
            banners.append((NOTE_COLOR, session.kept_edits_note))
        for note in (run.cache.thinning_note(), run.assembly_error):
            if note:
                banners.append((NOTE_COLOR, note))
        if self.tab == SHEET and self._sheet(session.current) is None:
            banners.append((NOTE_COLOR, "the Sheet tab plays the sheet once the run is done and assembled"))
        draw_banners(draw_list, origin, width, y, banners)

    def _draw_tag(self, draw_list, origin, width: int, tag: str) -> None:
        """A or B in the pane's top right corner, while there is a run to compare with."""
        white = imgui.get_color_u32(imgui.ImVec4(1.0, 1.0, 1.0, 0.95))
        draw_list.add_text(imgui.get_font(), imgui.get_font_size() * 2, imgui.ImVec2(origin.x + width - 36,
                                                                                     origin.y + 6), white, tag)

    # -- the light arrow ------------------------------------------------------------------------------------

    def _near_light_tip(self, camera: ViewCamera) -> bool:
        origin, length = light_arrow_span(self.session.derived)
        tip = camera.project(origin + self.session.viewport.toward_light_world * length)
        if tip is None:
            return False
        mouse = imgui.get_mouse_pos()
        return math.dist((mouse.x - self.pane_origin.x, mouse.y - self.pane_origin.y), tip) <= LIGHT_GRAB_PX

    def _release_light(self) -> None:
        """Applies the dragged light as an edit of `render.light_dir`, keeping its length."""
        self.input.drag = None
        preview, self.light_preview = self.light_preview, None
        session = self.session
        length = float(np.linalg.norm(session.recipe.render.light_dir))
        light_dir = light_dir_in_camera(preview, session.viewport.sheet_camera, length)
        self.panel.commit("render.light_dir", [round(float(value), 4) for value in light_dir])

    # -- window callbacks -----------------------------------------------------------------------------------

    def _post_init(self) -> None:
        io = imgui.get_io()
        io.config_flags &= ~imgui.ConfigFlags_.nav_enable_keyboard  # Space and the arrows belong to the viewer
        io.config_drag_click_to_input_text = True  # a click on a panel number (no drag) opens it for typing
        start_plotting()

    def _before_exit(self) -> None:
        self.textures.delete()
        stop_plotting()


def _sheet_key(snapshot: Snapshot) -> tuple:
    """What a Sheet tab card depends on: the run's frames and the recipe's look (a look edit makes a new
    viewport over the same run)."""
    return snapshot.run.serial, snapshot.viewport.serial
