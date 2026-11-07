"""Recipes for tests, built as tables so each test states only what it changes."""

import copy

from plume.recipe.load import fill_dependent_defaults, parse_recipe
from plume.recipe.schema import Recipe

BASE = {
    "seed": 1,
    "domain": {"size_m": [1.2, 1.2, 1.2], "cell_m": 0.05},
    "time": {"duration_s": 1.0, "frames": 4},
    "emitter": [{"name": "puff", "center_m": [0.0, 0.3, 0.0], "radius_m": 0.2, "end_s": 0.5,
                 "smoke_per_s": 5.0}],
}


def recipe_table(**changes) -> dict:
    """The base table with `changes` merged in; a section's change is a dict merged into that section."""
    table = copy.deepcopy(BASE)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(table.get(key), dict):
            table[key].update(value)
        else:
            table[key] = value
    return table


def tiny_recipe(**changes) -> Recipe:
    """A resolved recipe from the base table plus `changes`."""
    return fill_dependent_defaults(parse_recipe(recipe_table(**changes)), "tiny")
