"""The camera's mouse and keys in a viewport (spec V10), shared by the recipe window and the sheet-only
window: Alt + left, middle and right drags (tumble, track, dolly), the wheel, and the right-mouse free-look
with WASD/E/Q fly and the wheel's speed trim.

A plain left drag is the window's own (the light arrow, the slice plane): the window names it in `drag`
before calling `update`, ends it itself, and reads the mouse's motion meanwhile.
"""

import math

from imgui_bundle import imgui

from plume.view.navigation import Navigation

NAVIGATION_DRAGS = ("tumble", "track", "dolly")


class CameraInput:
    """The drag or free-look in progress and when the camera last moved."""

    def __init__(self):
        self.drag: str | None = None  # a navigation drag, or the window's own left drag
        self.free_look = False
        self.moved_s = -math.inf
        self.trim_changed_s = -math.inf

    @property
    def idle(self) -> bool:
        """No drag and no free-look: a press may start one."""
        return self.drag is None and not self.free_look

    def update(self, nav: Navigation, now: float, dt: float, hovered: bool, release_hit) -> None:
        """Applies this window update's camera input. `release_hit()` gives the pivot's new point when the
        right button is let go after a free-look (None: the domain's center)."""
        io = imgui.get_io()
        before = nav.pose()
        left, middle, right = imgui.MouseButton_.left, imgui.MouseButton_.middle, imgui.MouseButton_.right
        if hovered and self.idle:
            if io.key_alt and imgui.is_mouse_clicked(left):
                self.drag = "tumble"
            elif io.key_alt and imgui.is_mouse_clicked(middle):
                self.drag = "track"
            elif io.key_alt and imgui.is_mouse_clicked(right):
                self.drag = "dolly"
            elif imgui.is_mouse_clicked(right):
                self.free_look = True
                _capture_cursor(True)
        delta = io.mouse_delta
        if self.drag in NAVIGATION_DRAGS:
            button = {"tumble": left, "track": middle, "dolly": right}[self.drag]
            if not imgui.is_mouse_down(button):
                self.drag = None
            elif delta.x or delta.y:
                getattr(nav, self.drag)(delta.x, delta.y)
        forward = right_axis = up = 0.0
        if self.free_look:
            if not imgui.is_mouse_down(right) or imgui.is_key_pressed(imgui.Key.escape):
                self.free_look = False
                _capture_cursor(False)
                nav.release(release_hit())
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
        if nav.pose() != before:
            self.moved_s = now


def _axis(positive, negative) -> float:
    return float(imgui.is_key_down(positive)) - float(imgui.is_key_down(negative))


def _capture_cursor(captured: bool) -> None:
    """Hides and locks the cursor for free-look (GLFW reports unbounded motion meanwhile)."""
    import glfw
    from imgui_bundle import glfw_utils

    mode = glfw.CURSOR_DISABLED if captured else glfw.CURSOR_NORMAL
    glfw.set_input_mode(glfw_utils.glfw_window_hello_imgui(), glfw.CURSOR, mode)
