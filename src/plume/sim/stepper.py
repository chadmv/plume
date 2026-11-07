"""One simulation step, in the spec's order: emit, forces, advect velocity, project, advect scalars,
dissipate."""

from plume.recipe.schema import Recipe
from plume.sim.advect import advect_maccormack
from plume.sim.dissipate import dissipate
from plume.sim.emitters import emit, emitter_params
from plume.sim.forces import apply_buoyancy
from plume.sim.grid import Grid
from plume.sim.pressure import project


class Stepper:
    """Advances a grid by fixed steps of `dt` under a recipe's emitters, forces and dissipation."""

    def __init__(self, grid: Grid, recipe: Recipe, dt: float):
        self.grid = grid
        self.recipe = recipe
        self.dt = dt
        self.emitters = emitter_params(recipe.emitter, grid.device)

    def step(self, time_s: float) -> None:
        """Advances from `time_s` to `time_s + dt`."""
        grid, recipe, dt = self.grid, self.recipe, self.dt
        ambient = recipe.domain.ambient_k
        emit(grid, self.emitters, recipe.seed, time_s, dt)
        forces = recipe.forces
        apply_buoyancy(grid, forces.gravity_mps2, forces.heat_buoyancy, forces.smoke_weight, ambient, dt)
        self._advect_velocity()
        project(grid, recipe.solver.pressure_iterations)
        self._advect_scalars()
        dissipate(grid, recipe.dissipation.smoke_per_s, recipe.dissipation.cooling_per_s, ambient, dt)

    def _advect_velocity(self) -> None:
        fields = self.grid.velocity_fields()
        velocity = tuple(field.data for field in fields)
        for field in fields:
            advect_maccormack(field, velocity, self.grid, self.dt)
        for field in fields:
            field.swap()

    def _advect_scalars(self) -> None:
        velocity = tuple(field.data for field in self.grid.velocity_fields())
        for field in (self.grid.smoke, self.grid.temperature):
            advect_maccormack(field, velocity, self.grid, self.dt)
            field.swap()
