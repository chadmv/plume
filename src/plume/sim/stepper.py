"""One simulation step, in the spec's order: emit, forces, advect velocity, project, advect scalars,
dissipate."""

from plume.recipe.schema import Recipe
from plume.sim.advect import advect_maccormack
from plume.sim.conserve import SmokeBudget
from plume.sim.dissipate import dissipate
from plume.sim.emitters import emit, emitter_params
from plume.sim.forces import apply_buoyancy, apply_drag
from plume.sim.grid import Grid
from plume.sim.pressure import project
from plume.sim.pressure_solver import make_pressure_solve
from plume.sim.turbulence import apply_turbulence
from plume.sim.vorticity import VorticityConfinement


class Stepper:
    """Advances a grid one step at a time under a recipe's emitters, forces and dissipation."""

    def __init__(self, grid: Grid, recipe: Recipe):
        self.grid = grid
        self.recipe = recipe
        self.emitters = emitter_params(recipe.emitter, grid.device)
        self.pressure_solve = make_pressure_solve(grid, recipe.solver)
        self.smoke_budget = SmokeBudget(grid)
        self.confinement = VorticityConfinement(grid) if recipe.forces.vorticity_confinement > 0 else None

    def step(self, time_s: float, dt: float) -> None:
        """Advances from `time_s` to `time_s + dt`."""
        grid, recipe = self.grid, self.recipe
        ambient = recipe.domain.ambient_k
        emit(grid, self.emitters, recipe.seed, time_s, dt)
        forces = recipe.forces
        apply_buoyancy(grid, forces.gravity_mps2, forces.heat_buoyancy, forces.smoke_weight, ambient, dt)
        if self.confinement is not None:
            self.confinement.apply(grid, forces.vorticity_confinement, dt)
        turbulence = forces.turbulence
        apply_turbulence(grid, recipe.seed, turbulence.scale_m, turbulence.strength_mps2, turbulence.speed_mps,
                         time_s, dt)
        apply_drag(grid, forces.wind_mps, forces.drag_per_s, dt)
        self._advect_velocity(dt)
        project(grid, self.pressure_solve)
        self._advect_scalars(dt)
        dissipate(grid, recipe.dissipation.smoke_per_s, recipe.dissipation.cooling_per_s, ambient, dt)

    def _advect_velocity(self, dt: float) -> None:
        fields = self.grid.velocity_fields()
        velocity = tuple(field.data for field in fields)
        for field in fields:
            advect_maccormack(field, velocity, self.grid, dt)
        for field in fields:
            field.swap()

    def _advect_scalars(self, dt: float) -> None:
        velocity = tuple(field.data for field in self.grid.velocity_fields())
        advect_maccormack(self.grid.smoke, velocity, self.grid, dt)
        self.smoke_budget.hold(self.grid)
        self.grid.smoke.swap()
        advect_maccormack(self.grid.temperature, velocity, self.grid, dt)
        self.grid.temperature.swap()
