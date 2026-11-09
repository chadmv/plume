"""The viewer's camera: its state and the navigation rules, as pure math with no window.

Maya's viewport controls (Alt + left tumbles about the pivot, Alt + middle tracks, Alt + right and the
wheel dolly) plus a right-mouse free-look and WASD/E/Q fly in the manner of an editor camera (spec V10).
The pose is a pivot, a yaw and pitch, and the eye's distance from the pivot along the view axis: the eye
is always `pivot + toward * distance`. The basis is `render.camera.make_camera(pitch, yaw)`, the sheet
camera's own rule, so the sheet camera (Home) is the pose at the recipe's elevation and azimuth.

Signs: a drag to the right turns the scene to the right (yaw falls); a drag down shows more of the top
(pitch, the elevation, rises). Free-look turns the view the same way the mouse moves.
"""

import math
from dataclasses import dataclass

import numpy as np

from plume.render.camera import make_camera

FIELD_OF_VIEW_DEG = 40.0  # perspective, vertical
PITCH_LIMIT_DEG = 88.0
TURN_DEG_PER_PX = math.degrees(0.005)  # tumble and free-look
DOLLY_PER_PX = 0.005  # a drag's dolly is exponential: exp(-pixels * this)
WHEEL_NOTCH = 0.85  # one notch in multiplies the distance (perspective) or view size (orthographic) by this
FLY_RISE_S = 0.025  # time constants of the fly speed easing toward the keys' goal
FLY_FALL_S = 0.035
FLY_SETTLE = 1e-4  # a coasting fly stops once its speed is under this share of the trimmed speed
TRIM_STEP = 1.25
MIN_TRIM = 0.125
MAX_TRIM = 8.0
FRAME_MARGIN = 1.1  # F leaves this much room around what it frames
NEAREST_M_PER_SIZE = 0.002  # the closest the eye or the smallest view size, per meter of domain size
FARTHEST_PER_SIZE = 100.0


@dataclass(frozen=True)
class ViewCamera:
    """One view's camera over an image of `width_px` by `height_px`, as the ray march and the guides
    read it. The pixel rectangle (`left`, `top`, `pixel`) is on the camera plane through the world origin
    in meters (orthographic), or on the plane one meter in front of the eye (perspective)."""

    right: np.ndarray
    up: np.ndarray
    toward: np.ndarray  # from the scene toward the eye
    eye: np.ndarray
    perspective: bool
    left: float
    top: float
    pixel: float
    width_px: int
    height_px: int

    def project(self, point: np.ndarray) -> tuple[float, float] | None:
        """Continuous pixel coordinates (x right, y down) of a world point; None behind the eye."""
        if not self.perspective:
            return (float((point @ self.right - self.left) / self.pixel),
                    float((self.top - point @ self.up) / self.pixel))
        offset = point - self.eye
        ahead = -(offset @ self.toward)
        if ahead <= 1e-9:
            return None
        return (float((offset @ self.right / ahead - self.left) / self.pixel),
                float((self.top - offset @ self.up / ahead) / self.pixel))

    def ahead(self, point: np.ndarray) -> float:
        """How far in front of the eye a point is, along the view; orthographic views see everything."""
        return float(-((point - self.eye) @ self.toward)) if self.perspective else math.inf


class Navigation:
    """The camera's pose and every motion in flight, for one domain."""

    def __init__(self, domain_min_m: tuple, domain_size_m: tuple):
        self.domain_min = np.array(domain_min_m, dtype=np.float64)
        self.domain_size = np.array(domain_size_m, dtype=np.float64)
        self.domain_center = self.domain_min + self.domain_size / 2
        size = float(np.linalg.norm(self.domain_size))
        self.nearest = NEAREST_M_PER_SIZE * size
        self.farthest = FARTHEST_PER_SIZE * size
        self.pivot = self.domain_center.copy()
        self.yaw_deg = 0.0
        self.pitch_deg = 0.0
        self.distance = 2.0 * size
        self.half_height = size / 2
        self.perspective = False
        self.fly_trim = 1.0
        self.fly_velocity = np.zeros(3)
        self.width_px = 1
        self.height_px = 1

    # -- the pose ------------------------------------------------------------------------------------------

    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        camera = make_camera(self.pitch_deg, self.yaw_deg)
        return camera.right, camera.up, camera.toward

    def eye(self) -> np.ndarray:
        return self.pivot + self.basis()[2] * self.distance

    def pose(self) -> tuple:
        """Everything that decides what the view shows, to tell when the camera moved."""
        return (tuple(self.pivot), self.yaw_deg, self.pitch_deg, self.distance, self.half_height,
                self.perspective, self.width_px, self.height_px)

    def set_viewport(self, width_px: int, height_px: int) -> None:
        self.width_px = max(1, int(width_px))
        self.height_px = max(1, int(height_px))

    def view_camera(self, width_px: int | None = None, height_px: int | None = None) -> ViewCamera:
        """The camera over an image of the given size (the viewport's by default); a smaller image of the
        same aspect shows the same view at a coarser pixel."""
        width = width_px or self.width_px
        height = height_px or self.height_px
        right, up, toward = self.basis()
        aspect = width / height
        if self.perspective:
            half = math.tan(math.radians(FIELD_OF_VIEW_DEG) / 2)
            left, top = -half * aspect, half
        else:
            half = self.half_height
            left, top = float(self.pivot @ right) - half * aspect, float(self.pivot @ up) + half
        return ViewCamera(right=right, up=up, toward=toward, eye=self.eye(), perspective=self.perspective,
                          left=left, top=top, pixel=2.0 * half / height, width_px=width, height_px=height)

    # -- Maya --------------------------------------------------------------------------------------------

    def tumble(self, dx_px: float, dy_px: float) -> None:
        """Alt + left drag: turns the eye around the pivot."""
        self.yaw_deg -= dx_px * TURN_DEG_PER_PX
        self.pitch_deg = _clamp(self.pitch_deg + dy_px * TURN_DEG_PER_PX, -PITCH_LIMIT_DEG, PITCH_LIMIT_DEG)

    def track(self, dx_px: float, dy_px: float) -> None:
        """Alt + middle drag: slides the view so the scene at the pivot's depth follows the cursor."""
        right, up, _ = self.basis()
        meters_per_px = self._view_height_at_pivot() / self.height_px
        self.pivot = self.pivot + (-right * dx_px + up * dy_px) * meters_per_px

    def dolly(self, dx_px: float, dy_px: float) -> None:
        """Alt + right drag: right or up moves in, left or down out (orthographic: the view's size)."""
        self._scale_toward_pivot(math.exp(-(dx_px - dy_px) * DOLLY_PER_PX))

    def wheel(self, notches: float) -> None:
        """Wheel notches, positive in."""
        self._scale_toward_pivot(WHEEL_NOTCH**notches)

    def frame(self, center: np.ndarray, radius: float) -> None:
        """F and Shift+F: puts the pivot on `center` and fits a sphere of `radius` in the view."""
        self.pivot = np.array(center, dtype=np.float64)
        aspect = self.width_px / self.height_px
        reach = max(radius, self.nearest) * FRAME_MARGIN
        if self.perspective:
            half_vertical = math.radians(FIELD_OF_VIEW_DEG) / 2
            half_horizontal = math.atan(math.tan(half_vertical) * aspect)
            self.distance = _clamp(reach / math.sin(min(half_vertical, half_horizontal)), self.nearest, self.farthest)
        else:
            self.half_height = _clamp(reach * max(1.0, 1.0 / aspect), self.nearest, self.farthest)

    def home(self, elevation_deg: float, azimuth_deg: float, center_m: tuple[float, float],
             half_size_m: tuple[float, float]) -> None:
        """Home: the sheet camera, orthographic, fitting a rectangle of its camera plane (center and half
        width and height, in plane meters: the sheet's crop or its domain view)."""
        self.yaw_deg = azimuth_deg
        self.pitch_deg = elevation_deg
        self.perspective = False
        self.fly_velocity = np.zeros(3)
        right, up, toward = self.basis()
        depth = float(self.domain_center @ toward)
        self.pivot = right * center_m[0] + up * center_m[1] + toward * depth
        aspect = self.width_px / self.height_px
        self.half_height = max(half_size_m[1], half_size_m[0] / aspect)
        self.distance = self.half_height / math.tan(math.radians(FIELD_OF_VIEW_DEG) / 2)

    def toggle_perspective(self) -> None:
        """P: switches projection, keeping the view's size at the pivot."""
        self._set_perspective(not self.perspective)

    # -- free-look and fly ---------------------------------------------------------------------------------

    def look(self, dx_px: float, dy_px: float) -> None:
        """Right mouse held: turns the view about the eye, which stays put."""
        eye = self.eye()
        self.yaw_deg -= dx_px * TURN_DEG_PER_PX
        self.pitch_deg = _clamp(self.pitch_deg + dy_px * TURN_DEG_PER_PX, -PITCH_LIMIT_DEG, PITCH_LIMIT_DEG)
        self.pivot = eye - self.basis()[2] * self.distance

    def fly(self, forward: float, right: float, up: float, dt_s: float) -> None:
        """Right mouse + W/S (forward), D/A (right), E/Q (up), each -1, 0 or 1, over `dt_s` seconds.

        The velocity eases toward the keys' goal (one domain width a second times the trim) and the
        position integrates that ease exactly. The first key in an orthographic view switches to
        perspective, where flying forward shows."""
        pressing = forward != 0.0 or right != 0.0 or up != 0.0
        if pressing and not self.perspective:
            self._set_perspective(True)
        if dt_s <= 0.0 or (not pressing and not self.fly_velocity.any()):
            return
        right_axis, _, toward = self.basis()
        speed = float(self.domain_size[0]) * self.fly_trim
        goal = (-toward * forward + right_axis * right + np.array([0.0, up, 0.0])) * speed
        tau = FLY_RISE_S if pressing else FLY_FALL_S
        decay = math.exp(-dt_s / tau)
        carry = tau * (1.0 - decay)
        self.pivot = self.pivot + goal * dt_s + (self.fly_velocity - goal) * carry
        self.fly_velocity = goal + (self.fly_velocity - goal) * decay
        if not pressing and np.linalg.norm(self.fly_velocity) < FLY_SETTLE * speed:
            self.fly_velocity = np.zeros(3)

    def trim(self, notches: float) -> None:
        """Right mouse + wheel: the fly speed's trim, x1.25 a notch."""
        self.fly_trim = _clamp(self.fly_trim * TRIM_STEP**notches, MIN_TRIM, MAX_TRIM)

    def release(self, hit: np.ndarray | None) -> None:
        """Right mouse released: the pivot moves along the view axis to `hit` (the first smoke past half
        thickness under the screen's center, a point on that axis), or with no hit to the domain center's
        depth. In perspective the eye stays put, and a center behind the eye leaves the pose alone; in
        orthographic the eye's place changes nothing seen, so the pivot moves and the distance stays."""
        _, _, toward = self.basis()
        eye = self.eye()
        target = self.domain_center if hit is None else np.asarray(hit, dtype=np.float64)
        depth = float((eye - target) @ toward)
        if not self.perspective:
            self.pivot = self.pivot + toward * float((target - self.pivot) @ toward)
            return
        if hit is None and depth <= self.nearest:
            return
        self.distance = _clamp(depth, self.nearest, self.farthest)
        self.pivot = eye - toward * self.distance

    # -- helpers ---------------------------------------------------------------------------------------------

    def _view_height_at_pivot(self) -> float:
        if self.perspective:
            return 2.0 * self.distance * math.tan(math.radians(FIELD_OF_VIEW_DEG) / 2)
        return 2.0 * self.half_height

    def _scale_toward_pivot(self, factor: float) -> None:
        if self.perspective:
            self.distance = _clamp(self.distance * factor, self.nearest, self.farthest)
        else:
            self.half_height = _clamp(self.half_height * factor, self.nearest, self.farthest)

    def _set_perspective(self, perspective: bool) -> None:
        tangent = math.tan(math.radians(FIELD_OF_VIEW_DEG) / 2)
        if perspective and not self.perspective:
            self.distance = _clamp(self.half_height / tangent, self.nearest, self.farthest)
        elif self.perspective and not perspective:
            self.half_height = _clamp(self.distance * tangent, self.nearest, self.farthest)
        self.perspective = perspective


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def smoke_bounds(smoke: np.ndarray, domain_min_m: tuple, cell_m: float,
                 visible_density: float) -> tuple[np.ndarray, float] | None:
    """The center and radius (half the diagonal) of the box around every cell whose smoke is at least
    `visible_density`, for F; None when no cell is."""
    cells = np.argwhere(smoke >= visible_density)
    if cells.size == 0:
        return None
    low = np.array(domain_min_m, dtype=np.float64) + cells.min(axis=0) * cell_m
    high = np.array(domain_min_m, dtype=np.float64) + (cells.max(axis=0) + 1) * cell_m
    return (low + high) / 2, float(np.linalg.norm(high - low)) / 2
