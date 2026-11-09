"""The recipe as flat keys: what the editing panel lists and Compare diffs."""

import dataclasses
import typing

from plume.recipe.load import parse_recipe, resolve_table
from plume.recipe.schema import RENDER_STAGE, SIMULATION_STAGE, Recipe, field_info
from plume.recipe.variation import apply_values
from plume.view.recipe_keys import (CHOICE, FLOAT, READ_ONLY, TEXT, VECTOR, WHOLE, changed_paths, changed_stages,
                                    flat_values, table_paths, values_by_path)
from support.tiny import TINY

import tomllib


def tiny_table() -> dict:
    return tomllib.loads(TINY)


def leaf_count(cls: type) -> int:
    hints = typing.get_type_hints(cls)
    count = 0
    for field in dataclasses.fields(cls):
        if field_info(field)["section"]:
            count += leaf_count(hints[field.name])
        elif not (cls is Recipe and field.name in ("extends", "emitter")):
            count += 1
    return count


def test_every_schema_leaf_is_listed_once_with_emitters_by_name():
    recipe = parse_recipe(tiny_table())
    entries = flat_values(recipe)
    paths = [entry.info.path for entry in entries]
    assert len(paths) == len(set(paths))
    from plume.recipe.schema import EmitterSettings
    assert len(paths) == leaf_count(Recipe) + leaf_count(EmitterSettings)
    assert "emitter.puff.noise.strength" in paths and "forces.turbulence.scale_m" in paths
    kinds = {entry.info.path: entry.info.kind for entry in entries}
    assert kinds["seed"] == WHOLE and kinds["domain.cell_m"] == FLOAT and kinds["domain.size_m"] == VECTOR
    assert kinds["domain.faces.top"] == CHOICE and kinds["output.name"] == TEXT
    assert kinds["emitter.puff.name"] == READ_ONLY and kinds["look.smoke_ramp"] == READ_ONLY
    assert kinds["look.backgrounds.grass"] == READ_ONLY
    groups = {entry.info.path: entry.info.group for entry in entries}
    assert groups["seed"] == "" and groups["forces.turbulence.scale_m"] == "forces"
    assert groups["emitter.puff.radius_m"] == "emitter.puff"


def test_a_key_path_applies_through_the_set_grammar():
    table = apply_values(tiny_table(), {"emitter.puff.noise.strength": 0.2, "forces.turbulence.scale_m": 0.5})
    values = values_by_path(parse_recipe(table))
    assert values["emitter.puff.noise.strength"] == 0.2 and values["forces.turbulence.scale_m"] == 0.5


def test_changes_are_listed_with_their_stages():
    before = resolve_table(tiny_table(), "tiny")
    after = resolve_table(apply_values(tiny_table(), {"render.soften_px": 1.0}), "tiny")
    assert changed_paths(before, after) == ["render.soften_px"]
    assert changed_stages(before, after) == {RENDER_STAGE}
    both = resolve_table(apply_values(tiny_table(), {"render.soften_px": 1.0, "seed": 4}), "tiny")
    assert changed_stages(before, both) == {RENDER_STAGE, SIMULATION_STAGE}
    assert changed_paths(before, before) == []


def test_a_renamed_emitter_shows_as_changed_keys():
    before = resolve_table(tiny_table(), "tiny")
    renamed = tiny_table()
    renamed["emitter"][0]["name"] = "ember"
    renamed["camera"] = {"seat": "ember"}
    after = resolve_table(renamed, "tiny")
    paths = changed_paths(before, after)
    assert "emitter.ember.radius_m" in paths and "emitter.puff.radius_m" in paths


def test_the_keys_a_table_sets():
    paths = table_paths(tiny_table())
    assert {"seed", "domain.cell_m", "emitter.puff.noise.scale_m", "output.frame_px"} <= paths
    assert "forces.drag_per_s" not in paths
