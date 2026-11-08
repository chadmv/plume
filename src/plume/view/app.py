"""The viewer window: input, layout and the panels, around the session, navigation and viewport.

One window update does, in order: follow the recipe on disk and simulate one frame of a live run
(`Session.update`), move the playhead, apply the camera input, redraw the viewport if anything it shows
changed, and draw the bars. Every Warp launch happens here, on the window's thread.
"""

import math
import time

import numpy as np
import OpenGL.GL as gl
from imgui_bundle import hello_imgui, imgui

from plume import tool_label
from plume.recipe.schema import SHADE_LAYOUT
from plume.view.guides import BOX, EMITTER, LIGHT, TICK, dashes, guide_segments, on_screen
from plume.view.navigation import Navigation, smoke_bounds
from plume.view.session import Session
from plume.view.viewport import DARK_BACKGROUND, HEAT_VIEW, LOOK, SHADE_VIEW, THICKNESS_VIEW

WINDOW_SIZE = (1600, 900)
MOVING_S = 0.25  # the viewport draws at half resolution until the camera has been still this long
TRIM_SHOWN_S = 1.5
SPEEDS = (0.25, 0.5, 1.0, 2.0)
BOTTOM_BAR_PX = 64
GUIDE_COLORS = {BOX: (0.85, 0.85, 0.85, 0.55), TICK: (0.85, 0.85, 0.85, 0.55), EMITTER: (1.0, 0.6, 0.2, 0.8),
                LIGHT: (1.0, 0.9, 0.3, 0.9)}
ERROR_COLOR = (0.75, 0.12, 0.12, 0.9)
NOTE_COLOR = (0.55, 0.45, 0.1, 0.85)


def run_viewer(session: Session) -> None:
    """Opens the window and runs it until it is closed."""
    app = ViewerApp(session)
    hello_imgui.run(app.runner_params())


class ViewerApp:
    """The window's state between updates."""

    def __init__(self, session: Session):
        self.session = session
        self.view = LOOK
        self.background_index = 0
        self.show_guides = True
        self.playing = True
        self.speed = 1.0
        self.loop = True
        self.playhead = 0
        self.play_clock_s = 0.0
        self.nav: Navigation | None = None
        self.nav_needs_home = True
        self.domain = None
        self.run_seen = None
        self.drag: str | None = None
        self.free_look = False
        self.moved_s = -math.inf
        self.trim_changed_s = -math.inf
        self.drawn_key = None
        self.redraw_ms = 0.0
        self.drawn_half = False
        self.texture: int | None = None
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
        self._advance_playhead(dt)
        self._top_bar()
        self._viewport(now, dt)
        self._bottom_bar()

    def _follow_run(self) -> None:
        session = self.session
        domain = (session.derived.domain_min_m, session.derived.size_m)
        if domain != self.domain:
            self.domain = domain
            self.nav = Navigation(*domain)
            self.nav_needs_home = True
        if session.run is not self.run_seen:
            self.run_seen = session.run
            self.playhead = 0
            self.play_clock_s = 0.0
            self.drawn_key = None

    def _advance_playhead(self, dt: float) -> None:
        run = self.session.run
        kept = run.cache.kept_frames()
        if not kept:
            return
        if not run.done and not run.stopped:
            if self.playing:
                self.playhead = kept[-1]  # a live run's playhead follows the newest frame
            return
        if not self.playing:
            return
        self.play_clock_s += dt * self.speed
        frame_s = 1.0 / self.session.derived.fps
        while self.play_clock_s >= frame_s:
            self.play_clock_s -= frame_s
            later = [frame for frame in kept if frame > self.playhead]
            if later:
                self.playhead = later[0]
            elif self.loop:
                self.playhead = kept[0]
            else:
                self.playing = False
                self.play_clock_s = 0.0
                break

    # -- the bars -----------------------------------------------------------------------------------------

    def _top_bar(self) -> None:
        session = self.session
        imgui.text(str(session.recipe_path))
        imgui.same_line()
        imgui.text_disabled("| Volume")
        layout_name = "Shade" if session.recipe.output.channels == SHADE_LAYOUT else "Normal"
        for view, name in ((LOOK, "Look"), (HEAT_VIEW, "Heat"), (THICKNESS_VIEW, "Thickness"),
                           (SHADE_VIEW, layout_name)):
            imgui.same_line()
            if imgui.radio_button(f"{name} ({view + 1})", self.view == view):
                self.view = view
        imgui.same_line()
        _, self.show_guides = imgui.checkbox("Guides (G)", self.show_guides)
        imgui.same_line()
        if imgui.radio_button("Full", not session.preview):
            session.set_preview(False)
        imgui.same_line()
        if imgui.radio_button("Preview", session.preview):
            session.set_preview(True)
        imgui.same_line()
        if imgui.button(f"Background: {self._background_name()} (B)"):
            self.background_index = (self.background_index + 1) % 3
        imgui.same_line()
        if imgui.button("Persp (P)" if self.nav.perspective else "Ortho (P)"):
            self.nav.toggle_perspective()
        imgui.same_line()
        imgui.text_disabled(f"| {session.device} | {tool_label()}")

    def _bottom_bar(self) -> None:
        run = self.session.run
        frames = run.frames
        if imgui.button("Pause" if self.playing else "Play"):
            self.playing = not self.playing
        imgui.same_line()
        if imgui.button("|<"):
            self._step_to("first")
        imgui.same_line()
        if imgui.button("<"):
            self._step_to("previous")
        imgui.same_line()
        if imgui.button(">"):
            self._step_to("next")
        imgui.same_line()
        if imgui.button(">|"):
            self._step_to("last")
        imgui.same_line()
        imgui.set_next_item_width(90)
        if imgui.begin_combo("speed", f"{self.speed:g}x"):
            for speed in SPEEDS:
                if imgui.selectable(f"{speed:g}x", speed == self.speed)[0]:
                    self.speed = speed
            imgui.end_combo()
        imgui.same_line()
        _, self.loop = imgui.checkbox("loop", self.loop)
        imgui.same_line()
        landed = run.landed
        status = "done" if run.done else ("stopped" if run.stopped else "running")
        imgui.progress_bar(landed / frames, imgui.ImVec2(160, 0), f"run {landed}/{frames} {status}")
        imgui.set_next_item_width(-1)
        changed, frame = imgui.slider_int("##scrub", self.playhead, 0, frames - 1, "frame %d")
        if changed:
            nearest = run.cache.nearest_kept(min(frame, max(landed - 1, 0)))
            if nearest is not None:
                self.playhead = nearest
                self.playing = False

    # -- the viewport ---------------------------------------------------------------------------------------

    def _viewport(self, now: float, dt: float) -> None:
        size = imgui.get_content_region_avail()
        width, height = int(size.x), int(size.y) - BOTTOM_BAR_PX
        if width < 8 or height < 8:
            return
        self.nav.set_viewport(width, height)
        if self.nav_needs_home:
            self._home()
            self.nav_needs_home = False
        origin = imgui.get_cursor_screen_pos()
        self._redraw(now, width, height)
        imgui.image(imgui.ImTextureRef(self.texture), imgui.ImVec2(width, height))
        hovered = imgui.is_item_hovered()
        self._camera_input(now, dt, hovered)
        draw_list = imgui.get_window_draw_list()
        draw_list.push_clip_rect(origin, imgui.ImVec2(origin.x + width, origin.y + height), True)
        if self.show_guides:
            self._draw_guides(draw_list, origin)
        self._draw_overlay(draw_list, origin, width, now)
        draw_list.pop_clip_rect()

    def _redraw(self, now: float, width: int, height: int) -> None:
        session = self.session
        run = session.run
        frame = run.cache.nearest_kept(self.playhead)
        if frame is None:
            if self.texture is None:
                self._upload(np.zeros((1, 1, 4), dtype=np.uint8))
            return
        half = now - self.moved_s < MOVING_S
        key = (run.serial, frame, self.nav.pose(), self.view, self.background_index, half, run.heat_divisor,
               run.shade_divisor)
        if key == self.drawn_key:
            return
        started = time.perf_counter()
        camera = self.nav.view_camera(max(1, width // 2), max(1, height // 2)) if half else self.nav.view_camera()
        image = session.viewport.draw(run, frame, camera, self.view, self._background_hex())
        self._upload(image)
        self.redraw_ms = (time.perf_counter() - started) * 1000.0
        self.drawn_half = half
        self.drawn_key = key

    def _upload(self, image: np.ndarray) -> None:
        if self.texture is None:
            self.texture = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        height, width = image.shape[:2]
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                        np.ascontiguousarray(image))

    def _camera_input(self, now: float, dt: float, hovered: bool) -> None:
        io = imgui.get_io()
        nav = self.nav
        before = nav.pose()
        left, middle, right = imgui.MouseButton_.left, imgui.MouseButton_.middle, imgui.MouseButton_.right
        if hovered and self.drag is None and not self.free_look:
            if io.key_alt and imgui.is_mouse_clicked(left):
                self.drag = "tumble"
            elif io.key_alt and imgui.is_mouse_clicked(middle):
                self.drag = "track"
            elif io.key_alt and imgui.is_mouse_clicked(right):
                self.drag = "dolly"
            elif imgui.is_mouse_clicked(right):
                self._start_free_look()
        delta = io.mouse_delta
        if self.drag is not None:
            button = {"tumble": left, "track": middle, "dolly": right}[self.drag]
            if not imgui.is_mouse_down(button):
                self.drag = None
            elif delta.x or delta.y:
                getattr(nav, self.drag)(delta.x, delta.y)
        forward = right_axis = up = 0.0
        if self.free_look:
            if not imgui.is_mouse_down(right) or imgui.is_key_pressed(imgui.Key.escape):
                self._end_free_look()
            else:
                if delta.x or delta.y:
                    nav.look(delta.x, delta.y)
                forward = _axis(imgui.Key.w, imgui.Key.s)
                right_axis = _axis(imgui.Key.d, imgui.Key.a)
                up = _axis(imgui.Key.e, imgui.Key.q)
                if io.mouse_wheel:
                    nav.trim(io.mouse_wheel)
                    self.trim_changed_s = now
        elif hovered and io.mouse_wheel:
            nav.wheel(io.mouse_wheel)
        nav.fly(forward, right_axis, up, dt)
        if not self.free_look and not io.want_text_input:
            self._keys(io)
        if nav.pose() != before:
            self.moved_s = now

    def _keys(self, io) -> None:
        pressed = imgui.is_key_pressed
        if pressed(imgui.Key.space, False):
            self.playing = not self.playing
        if pressed(imgui.Key.comma):
            self._step_to("first" if io.key_shift else "previous")
        if pressed(imgui.Key.period):
            self._step_to("last" if io.key_shift else "next")
        for key, view in ((imgui.Key._1, LOOK), (imgui.Key._2, HEAT_VIEW), (imgui.Key._3, THICKNESS_VIEW),
                          (imgui.Key._4, SHADE_VIEW)):
            if pressed(key, False):
                self.view = view
        if pressed(imgui.Key.g, False):
            self.show_guides = not self.show_guides
        if pressed(imgui.Key.b, False):
            self.background_index = (self.background_index + 1) % 3
        if pressed(imgui.Key.p, False):
            self.nav.toggle_perspective()
        if pressed(imgui.Key.home, False):
            self._home()
        if pressed(imgui.Key.f, False):
            self._frame(whole_domain=io.key_shift)

    def _step_to(self, where: str) -> None:
        kept = self.session.run.cache.kept_frames()
        if not kept:
            return
        self.playing = False
        if where == "first":
            self.playhead = kept[0]
        elif where == "last":
            self.playhead = kept[-1]
        elif where == "next":
            self.playhead = next((frame for frame in kept if frame > self.playhead), kept[-1])
        else:
            self.playhead = next((frame for frame in reversed(kept) if frame < self.playhead), kept[0])

    def _home(self) -> None:
        """The sheet camera, framing the sheet's crop once the run is assembled, else its domain view."""
        session = self.session
        view = session.run.view
        assembled = session.run.assembled
        if assembled is not None:
            crop = assembled.crop
            center_px = (crop.left + crop.side / 2, crop.top + crop.side / 2)
            half = (crop.side * view.pixel_m / 2, crop.side * view.pixel_m / 2)
        else:
            center_px = (view.width_px / 2, view.height_px / 2)
            half = (view.width_px * view.pixel_m / 2, view.height_px * view.pixel_m / 2)
        center = (view.left_m + center_px[0] * view.pixel_m, view.top_m - center_px[1] * view.pixel_m)
        camera = session.recipe.camera
        self.nav.home(camera.elevation_deg, camera.azimuth_deg, center, half)

    def _frame(self, whole_domain: bool) -> None:
        session = self.session
        nav = self.nav
        bounds = None
        frame = session.run.cache.nearest_kept(self.playhead)
        if not whole_domain and frame is not None:
            smoke = session.viewport.smoke_on_host(session.run, frame)
            bounds = smoke_bounds(smoke, session.derived.domain_min_m, session.recipe.domain.cell_m,
                                  session.viewport.visible_density())
        if bounds is None:
            bounds = (nav.domain_center, float(np.linalg.norm(nav.domain_size)) / 2)
        nav.frame(*bounds)

    def _start_free_look(self) -> None:
        self.free_look = True
        _capture_cursor(True)

    def _end_free_look(self) -> None:
        self.free_look = False
        _capture_cursor(False)
        session = self.session
        frame = session.run.cache.nearest_kept(self.playhead)
        hit = None
        if frame is not None:
            hit = session.viewport.center_hit(session.run, frame, self.nav.view_camera())
        self.nav.release(hit)

    # -- drawing over the viewport --------------------------------------------------------------------------

    def _draw_guides(self, draw_list, origin) -> None:
        session = self.session
        camera = self.nav.view_camera()
        segments = guide_segments(session.recipe, session.derived, self.playhead,
                                  session.viewport.toward_light_world)
        for segment in segments:
            ends = on_screen(camera, segment)
            if ends is None:
                continue
            color = imgui.get_color_u32(imgui.ImVec4(*GUIDE_COLORS[segment.kind]))
            pieces = dashes(*ends) if segment.dashed else [ends]
            for start, end in pieces:
                draw_list.add_line(imgui.ImVec2(origin.x + start[0], origin.y + start[1]),
                                   imgui.ImVec2(origin.x + end[0], origin.y + end[1]), color, 1.5)

    def _draw_overlay(self, draw_list, origin, width: int, now: float) -> None:
        session = self.session
        run = session.run
        derived = session.derived
        white = imgui.get_color_u32(imgui.ImVec4(1.0, 1.0, 1.0, 0.95))
        frame = run.cache.nearest_kept(self.playhead)
        lines = [
            f"{'Persp' if self.nav.perspective else 'Ortho'}   frame {frame if frame is not None else '-'}"
            f" / {run.frames - 1}   t {derived.frame_time_s(frame or 0):.3f} s",
            f"redraw {self.redraw_ms:.1f} ms{' (half)' if self.drawn_half else ''}   "
            f"run {session.run_seconds:.2f} s",
        ]
        if now - self.trim_changed_s < TRIM_SHOWN_S:
            lines.append(f"fly speed x{self.nav.fly_trim:.2f}")
        for row, text in enumerate(lines):
            draw_list.add_text(imgui.ImVec2(origin.x + 8, origin.y + 6 + row * 18), white, text)
        banners = []
        if session.error:
            banners.append((ERROR_COLOR, session.error))
        for note in (run.cache.thinning_note(), run.assembly_error):
            if note:
                banners.append((NOTE_COLOR, note))
        y = origin.y + 6 + len(lines) * 18 + 4
        for color, text in banners:
            text_size = imgui.calc_text_size(text, wrap_width=width - 32)
            draw_list.add_rect_filled(imgui.ImVec2(origin.x + 8, y),
                                      imgui.ImVec2(origin.x + 24 + text_size.x, y + text_size.y + 8),
                                      imgui.get_color_u32(imgui.ImVec4(*color)))
            draw_list.add_text(imgui.get_font(), imgui.get_font_size(), imgui.ImVec2(origin.x + 16, y + 4),
                               white, text, wrap_width=width - 32)
            y += text_size.y + 12

    # -- helpers ---------------------------------------------------------------------------------------------

    def _background_hex(self) -> str:
        backgrounds = self.session.recipe.look.backgrounds
        return (backgrounds.neutral, backgrounds.grass, DARK_BACKGROUND)[self.background_index]

    def _background_name(self) -> str:
        return ("neutral", "grass", "dark")[self.background_index]

    def _post_init(self) -> None:
        io = imgui.get_io()
        io.config_flags &= ~imgui.ConfigFlags_.nav_enable_keyboard  # Space and the arrows belong to the viewer

    def _before_exit(self) -> None:
        if self.texture is not None:
            gl.glDeleteTextures([self.texture])
            self.texture = None


def _axis(positive, negative) -> float:
    return float(imgui.is_key_down(positive)) - float(imgui.is_key_down(negative))


def _capture_cursor(captured: bool) -> None:
    """Hides and locks the cursor for free-look (GLFW reports unbounded motion meanwhile)."""
    import glfw
    from imgui_bundle import glfw_utils

    mode = glfw.CURSOR_DISABLED if captured else glfw.CURSOR_NORMAL
    glfw.set_input_mode(glfw_utils.glfw_window_hello_imgui(), glfw.CURSOR, mode)
