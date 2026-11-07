import tomllib

import pytest

from plume.cli.main import EXIT_OK, EXIT_RECIPE_ERROR, main
from plume.recipe.derived import derive
from plume.recipe.errors import RecipeError
from plume.recipe.load import load_recipe, load_recipe_with_origin, parse_recipe
from plume.recipe.serialize import recipe_to_toml

PARENT = """
seed = 4

[domain]
size_m = [2.0, 3.0, 2.0]
cell_m = 0.1
faces = { top = "open", left = "closed" }

[time]
duration_s = 2.0

[[emitter]]
name = "puff"
center_m = [0.0, 0.3, 0.0]
radius_m = 0.25
end_s = 0.25
smoke_per_s = 4.0
noise = { scale_m = 0.2, strength = 0.5 }

[dissipation]
smoke_per_s = 1.0
"""


def write(folder, name, text):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text)
    return path


def test_child_overrides_one_key_and_inherits_the_rest(tmp_path):
    write(tmp_path, "base.toml", PARENT)
    child = write(tmp_path, "child.toml", 'extends = "base.toml"\n[dissipation]\nsmoke_per_s = 2.5\n')
    recipe = load_recipe(child)
    assert recipe.dissipation.smoke_per_s == 2.5
    assert recipe.seed == 4
    assert recipe.emitter[0].smoke_per_s == 4.0
    assert recipe.extends == ""
    assert recipe.output.name == "child"


def test_nested_tables_merge_key_by_key(tmp_path):
    write(tmp_path, "base.toml", PARENT)
    child = write(tmp_path, "child.toml", 'extends = "base.toml"\n[domain.faces]\nright = "closed"\n')
    faces = load_recipe(child).domain.faces
    assert (faces.left, faces.right, faces.top) == ("closed", "closed", "open")


def test_child_emitter_list_replaces_the_parents(tmp_path):
    write(tmp_path, "base.toml", PARENT)
    child = write(tmp_path, "child.toml", 'extends = "base.toml"\n[[emitter]]\nname = "other"\n'
                                          'center_m = [0.0, 0.5, 0.0]\nradius_m = 0.1\nend_s = 0.5\n')
    recipe = load_recipe(child)
    assert [e.name for e in recipe.emitter] == ["other"]
    assert recipe.emitter[0].smoke_per_s == 0.0


def test_grandparent_chain_resolves_relative_to_each_file(tmp_path):
    write(tmp_path / "shared", "base.toml", PARENT)
    write(tmp_path / "shared", "middle.toml", 'extends = "base.toml"\nseed = 9\n')
    child = write(tmp_path / "effects", "child.toml", 'extends = "../shared/middle.toml"\n'
                                                      '[time]\nframes = 32\n')
    recipe, origin = load_recipe_with_origin(child)
    assert (recipe.seed, recipe.time.frames, recipe.time.duration_s) == (9, 32, 2.0)
    assert origin.extends_chain == ("../shared/middle.toml", "base.toml")


def test_a_loop_fails(tmp_path):
    write(tmp_path, "a.toml", 'extends = "b.toml"\n')
    write(tmp_path, "b.toml", 'extends = "a.toml"\n')
    with pytest.raises(RecipeError, match="loop"):
        load_recipe(tmp_path / "a.toml")


@pytest.mark.parametrize("parent", ["/etc/base.toml", "C:/recipes/base.toml", "C:base.toml",
                                    "\\\\server\\share\\base.toml"])
def test_an_absolute_parent_path_fails(tmp_path, parent):
    child = write(tmp_path, "child.toml", f"extends = '{parent}'\n")
    with pytest.raises(RecipeError, match="relative"):
        load_recipe(child)


def test_a_parent_that_is_not_toml_fails(tmp_path):
    child = write(tmp_path, "child.toml", 'extends = "base.txt"\n')
    with pytest.raises(RecipeError, match=".toml"):
        load_recipe(child)


def test_a_missing_parent_fails_naming_its_path(tmp_path):
    child = write(tmp_path, "child.toml", 'extends = "missing.toml"\n')
    with pytest.raises(RecipeError, match="missing.toml"):
        load_recipe(child)


def test_set_overrides_numbers_vectors_text_and_emitters(tmp_path):
    path = write(tmp_path, "base.toml", PARENT)
    recipe = load_recipe(path, sets=(
        "dissipation.cooling_per_s=0.5",
        "emitter.puff.velocity_mps=[0, 1.5, 0]",
        "emitter[0].radius_m = 0.4",
        "emitter.puff.noise.strength=0.9",
        "domain.faces.top=closed",
        "output.name=variant",
    ))
    assert recipe.dissipation.cooling_per_s == 0.5
    assert recipe.emitter[0].velocity_mps == (0.0, 1.5, 0.0)
    assert recipe.emitter[0].radius_m == 0.4
    assert recipe.emitter[0].noise.strength == 0.9
    assert recipe.domain.faces.top == "closed"
    assert recipe.output.name == "variant"


def test_set_applies_after_extends(tmp_path):
    write(tmp_path, "base.toml", PARENT)
    child = write(tmp_path, "child.toml", 'extends = "base.toml"\nseed = 5\n')
    assert load_recipe(child, sets=("seed=6",)).seed == 6


def test_set_of_an_unknown_key_names_the_closest(tmp_path):
    path = write(tmp_path, "base.toml", PARENT)
    with pytest.raises(RecipeError, match="did you mean cooling_per_s"):
        load_recipe(path, sets=("dissipation.cooling_per=0.5",))


@pytest.mark.parametrize("item, message", [
    ("seed", "key=value"),
    ("emitter.nobody.radius_m=1", "no emitter is named 'nobody'"),
    ("emitter[3].radius_m=1", r"emitter\[3\] does not exist"),
    ("emitter.puff=1", "name the emitter"),
    ("seed.x=1", "is a value, not a table"),
    ("extends=other.toml", "cannot change extends"),
])
def test_malformed_sets_fail(tmp_path, item, message):
    path = write(tmp_path, "base.toml", PARENT)
    with pytest.raises(RecipeError, match=message):
        load_recipe(path, sets=(item,))


def test_set_leaves_a_parent_table_unchanged(tmp_path):
    from plume.recipe.variation import apply_sets

    table = tomllib.loads(PARENT)
    apply_sets(table, ("emitter.puff.noise.strength=0.1", "domain.faces.top=closed"))
    assert table["emitter"][0]["noise"]["strength"] == 0.5
    assert table["domain"]["faces"]["top"] == "open"


def test_settings_log_of_a_variation_loads_back_to_the_same_recipe(tmp_path):
    write(tmp_path, "base.toml", PARENT)
    child = write(tmp_path, "child.toml", 'extends = "base.toml"\nseed = 5\n')
    recipe, origin = load_recipe_with_origin(child, sets=("forces.heat_buoyancy=2",))
    text = recipe_to_toml(recipe, derive(recipe), device="cpu", origin=origin)
    table = tomllib.loads(text)
    assert table["resolved"]["extends_chain"] == ["base.toml"]
    assert table["resolved"]["sets"] == ["forces.heat_buoyancy=2"]
    assert parse_recipe(table) == recipe


def test_cli_check_takes_set_and_reports_bad_sets_with_exit_code_2(tmp_path, capsys):
    path = write(tmp_path, "base.toml", PARENT)
    assert main(["check", str(path), "--set", "seed=11", "--set", "time.frames=8"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "seed = 11" in out and "frames = 8" in out
    assert main(["check", str(path), "--set", "sed=11"]) == EXIT_RECIPE_ERROR
    assert "did you mean seed" in capsys.readouterr().err
