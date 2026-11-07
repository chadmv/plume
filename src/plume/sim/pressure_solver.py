"""Choosing the pressure solve a recipe asks for."""

from plume.recipe.schema import SolverSettings
from plume.sim.grid import Grid
from plume.sim.multigrid import Multigrid
from plume.sim.pressure import GaussSeidel, PressureSolve


def make_pressure_solve(grid: Grid, solver: SolverSettings) -> PressureSolve:
    """The solve for `grid`; multigrid allocates its coarse levels here, once per run."""
    if solver.pressure_solver == "gauss_seidel":
        return GaussSeidel(solver.pressure_iterations)
    return Multigrid(grid, solver.multigrid_cycles, solver.multigrid_sweeps)
