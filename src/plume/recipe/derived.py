"""Values computed from a resolved recipe: grid cell counts, the actual domain size, and timing."""

from dataclasses import dataclass

from plume.recipe.schema import Recipe


@dataclass(frozen=True)
class Derived:
    cells: tuple[int, int, int]
    size_m: tuple[float, float, float]
    domain_min_m: tuple[float, float, float]
    fps: float
    dt_s: float
    warmup_steps: int
    steps_per_frame: int

    def frame_time_s(self, frame: int) -> float:
        """Effect time a frame shows, counted from the end of warmup: frames end at the duration."""
        return (frame + 1) / self.fps


def derive(recipe: Recipe) -> Derived:
    """Computes the derived values of a resolved recipe."""
    cell = recipe.domain.cell_m
    cells = tuple(max(1, round(size / cell)) for size in recipe.domain.size_m)
    size = tuple(count * cell for count in cells)
    fps = recipe.time.frames / recipe.time.duration_s
    dt = 1.0 / (fps * recipe.time.substeps)
    return Derived(
        cells=cells,
        size_m=size,
        domain_min_m=(-size[0] / 2, 0.0, -size[2] / 2),
        fps=fps,
        dt_s=dt,
        warmup_steps=round(recipe.time.warmup_s / dt),
        steps_per_frame=recipe.time.substeps,
    )
