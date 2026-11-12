"""The ray march: one ray per view pixel, front to back through the volume, fixed half-cell steps.

The sheet's view is orthographic: parallel rays from the camera plane, over the domain view. The viewer can
also ask for a perspective view: rays from an eye through a plane one meter in front of it, starting at the
eye when it is inside the domain. The march along each ray is the same for both.

Each ray gathers three things:
- thickness: how much the smoke blocks the ray (Beer-Lambert), the sheet's G;
- heat: glow from hot gas, hidden by smoke in front of it, the sheet's R before normalization;
- by layout, either the shade (the key light reaching each sample, from the light volume, lifted by the
  fill share) or the normal (the smoke's surface direction), each averaged with the weight the sample adds
  to the opacity.
"""

import warp as wp

from plume.render import raw_frame
from plume.sim.grid import GridInfo
from plume.sim.sample import sample_index_space

FAR_M = 1.0e4  # how far toward the camera rays start, well outside any domain
HEAT = wp.constant(raw_frame.HEAT)
THICKNESS = wp.constant(raw_frame.THICKNESS)
NORMAL_X = wp.constant(raw_frame.NORMAL_X)
NORMAL_Y = wp.constant(raw_frame.NORMAL_Y)
NORMAL_Z = wp.constant(raw_frame.NORMAL_Z)
SHADE = wp.constant(raw_frame.SHADE)


@wp.struct
class ViewParams:
    """The pixel rectangle on the camera plane (orthographic) or on the plane one meter in front of the
    eye (perspective), in the camera's basis."""

    right: wp.vec3
    up: wp.vec3
    toward: wp.vec3
    left_m: float
    top_m: float
    pixel_m: float
    perspective: int  # 0: parallel rays along -toward; 1: rays from `eye`
    eye: wp.vec3


@wp.struct
class LookParams:
    opacity_per_density: float
    glow_start_k: float
    smoke_hides_heat: float
    normal_fade_thickness: float
    shade_layout: int  # 1: write shade (reads `light`); 0: write the normal (reads `gradient`)
    shade_fill: float


@wp.func
def slab_range(origin: wp.vec3, direction: wp.vec3, box_min: wp.vec3, box_max: wp.vec3) -> wp.vec2:
    """Entry and exit distances of a ray through a box (entry > exit when it misses)."""
    t_enter = float(-1.0e30)
    t_exit = float(1.0e30)
    for axis in range(3):
        if wp.abs(direction[axis]) < 1.0e-12:
            if origin[axis] < box_min[axis] or origin[axis] > box_max[axis]:
                return wp.vec2(1.0, 0.0)
        else:
            t0 = (box_min[axis] - origin[axis]) / direction[axis]
            t1 = (box_max[axis] - origin[axis]) / direction[axis]
            t_enter = wp.max(t_enter, wp.min(t0, t1))
            t_exit = wp.min(t_exit, wp.max(t0, t1))
    return wp.vec2(t_enter, t_exit)


@wp.func
def pixel_ray(view: ViewParams, px: int, py: int):
    """The ray through a pixel's center: its origin and unit direction (the slice plane casts the same
    rays as the march)."""
    plane_x = view.left_m + (float(px) + 0.5) * view.pixel_m
    plane_y = view.top_m - (float(py) + 0.5) * view.pixel_m
    origin = view.right * plane_x + view.up * plane_y + view.toward * FAR_M
    direction = -view.toward
    if view.perspective == 1:
        origin = view.eye
        direction = wp.normalize(view.right * plane_x + view.up * plane_y - view.toward)
    return origin, direction


@wp.kernel
def raymarch_kernel(smoke: wp.array3d(dtype=float), temperature: wp.array3d(dtype=float),
                    gradient: wp.array3d(dtype=wp.vec3), light: wp.array3d(dtype=float), info: GridInfo,
                    view: ViewParams, look: LookParams, image: wp.array3d(dtype=float)):
    py, px = wp.tid()
    origin, direction = pixel_ray(view, px, py)
    box_max = info.origin_m + wp.vec3(float(info.dims[0]), float(info.dims[1]), float(info.dims[2])) * info.cell_m
    span = slab_range(origin, direction, info.origin_m, box_max)
    if view.perspective == 1:
        span = wp.vec2(wp.max(span[0], 0.0), span[1])  # nothing behind the eye

    transmittance = float(1.0)
    heat = float(0.0)
    normal_sum = wp.vec3(0.0, 0.0, 0.0)
    shade_sum = float(0.0)
    if span[1] > span[0]:
        length = span[1] - span[0]
        steps = int(wp.ceil(length / (0.5 * info.cell_m)))
        step_m = length / float(steps)
        for s in range(steps):
            position = origin + direction * (span[0] + (float(s) + 0.5) * step_m)
            g = (position - info.origin_m) / info.cell_m - wp.vec3(0.5, 0.5, 0.5)
            density = wp.max(sample_index_space(smoke, g), 0.0)
            alpha = 1.0 - wp.exp(-look.opacity_per_density * density * step_m)
            glow = wp.max(sample_index_space(temperature, g) - look.glow_start_k, 0.0)
            heat = heat + glow * step_m * wp.pow(transmittance, look.smoke_hides_heat)
            if look.shade_layout == 1:
                lit = look.shade_fill + (1.0 - look.shade_fill) * sample_index_space(light, g)
                shade_sum = shade_sum + transmittance * alpha * lit
            else:
                slope = sample_index_space(gradient, g)
                if alpha > 0.0 and wp.length(slope) > 1.0e-9:
                    normal_sum = normal_sum - transmittance * alpha * wp.normalize(slope)
            transmittance = transmittance * (1.0 - alpha)

    thickness = 1.0 - transmittance
    image[py, px, HEAT] = heat
    image[py, px, THICKNESS] = thickness
    if look.shade_layout == 1:
        image[py, px, SHADE] = shade_sum  # shade times thickness (raw_frame.py)
        image[py, px, NORMAL_Y] = 0.0  # the shade layout leaves the last two slots empty
        image[py, px, NORMAL_Z] = 0.0
        return
    facing = wp.vec3(0.0, 0.0, 1.0)
    normal = facing
    camera_normal = wp.vec3(wp.dot(normal_sum, view.right), wp.dot(normal_sum, view.up),
                            wp.dot(normal_sum, view.toward))
    if wp.length(camera_normal) > 1.0e-9:
        normal = wp.normalize(camera_normal)
        normal = wp.vec3(normal[0], normal[1], wp.abs(normal[2]))
        weight = wp.clamp(thickness / look.normal_fade_thickness, 0.0, 1.0)
        normal = wp.normalize(wp.lerp(facing, normal, weight))
    image[py, px, NORMAL_X] = normal[0]
    image[py, px, NORMAL_Y] = normal[1]
    image[py, px, NORMAL_Z] = normal[2]
