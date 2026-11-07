import tomllib

import pytest

from plume.recipe.derived import derive
from plume.recipe.errors import RecipeError
from plume.recipe.load import load_recipe, parse_recipe, preview_substeps
from plume.recipe.serialize import recipe_to_toml

MINIMAL = """
[domain]
size_m = [2.0, 3.0, 2.0]
cell_m = 0.02

[time]
duration_s = 3.2

[[emitter]]
name = "puff"
center_m = [0.0, 0.3, 0.0]
radius_m = 0.25
end_s = 0.25
"""


def write(tmp_path, text, name="puff_test.toml"):
    path = tmp_path / name
    path.write_text(text)
    return path


def test_minimal_recipe_resolves_with_defaults(tmp_path):
    recipe = load_recipe(write(tmp_path, MINIMAL))
    assert recipe.time.frames == 64
    assert recipe.output.columns == 8
    assert recipe.output.name == "puff_test"
    assert recipe.camera.seat == "puff"
    assert recipe.emitter[0].temperature_k == 293.0
    assert recipe.domain.faces.bottom == "closed"
    assert recipe.domain.faces.top == "open"


def test_derived_grid_and_timing(tmp_path):
    derived = derive(load_recipe(write(tmp_path, MINIMAL)))
    assert derived.cells == (100, 150, 100)
    assert derived.fps == pytest.approx(20.0)
    assert derived.dt_s == pytest.approx(1.0 / 60.0)
    assert derived.domain_min_m == pytest.approx((-1.0, 0.0, -1.0))


def test_typo_names_the_closest_key(tmp_path):
    text = MINIMAL.replace("radius_m", "radius_n")
    with pytest.raises(RecipeError, match=r"emitter\[0\]\.radius_n; did you mean radius_m"):
        load_recipe(write(tmp_path, text))


def test_missing_required_value_is_named(tmp_path):
    text = MINIMAL.replace("size_m = [2.0, 3.0, 2.0]\n", "")
    with pytest.raises(RecipeError, match=r"domain\.size_m is required"):
        load_recipe(write(tmp_path, text))


def test_wrong_type_is_named(tmp_path):
    text = MINIMAL.replace("duration_s = 3.2", 'duration_s = "long"')
    with pytest.raises(RecipeError, match=r"time\.duration_s must be a number"):
        load_recipe(write(tmp_path, text))


def test_bad_choice_lists_the_valid_ones(tmp_path):
    text = MINIMAL + '\n[domain.faces]\ntop = "shut"\n'
    text = text.replace("[domain]\n", "[domain]\n", 1)
    with pytest.raises(RecipeError, match=r"domain\.faces\.top must be one of closed, open"):
        load_recipe(write(tmp_path, text))


def test_single_emitter_table_hints_at_array_syntax(tmp_path):
    text = MINIMAL.replace("[[emitter]]", "[emitter]")
    with pytest.raises(RecipeError, match=r"\[\[emitter\]\]"):
        load_recipe(write(tmp_path, text))


def test_unknown_seat_is_rejected(tmp_path):
    text = MINIMAL + '\n[camera]\nseat = "nowhere"\n'
    with pytest.raises(RecipeError, match=r"camera\.seat 'nowhere' is not an emitter"):
        load_recipe(write(tmp_path, text))


@pytest.mark.parametrize("name", ["../escape", "a/b", "..", "C:evil", " spaced"])
def test_output_name_must_be_a_plain_name(tmp_path, name):
    text = MINIMAL + f'\n[output]\nname = "{name}"\n'
    with pytest.raises(RecipeError, match=r"output\.name must be a plain name"):
        load_recipe(write(tmp_path, text))


def test_preview_coarsens_the_longest_axis_to_48_cells(tmp_path):
    recipe = load_recipe(write(tmp_path, MINIMAL), preview=True)
    derived = derive(recipe)
    assert max(derived.cells) == 48
    assert recipe.time.frames == 16
    assert recipe.output.frame_px == 128
    assert recipe.output.columns == 4
    assert derived.fps == pytest.approx(5.0)


def test_preview_keeps_the_full_run_step_length(tmp_path):
    full = derive(load_recipe(write(tmp_path, MINIMAL)))
    preview = derive(load_recipe(write(tmp_path, MINIMAL), preview=True))
    assert preview.steps_per_frame == 12  # 64 frames x 3 substeps spread over 16 frames
    assert preview.dt_s == pytest.approx(full.dt_s)
    assert preview.warmup_steps == full.warmup_steps


def test_preview_substeps_round_up_so_steps_are_never_longer():
    assert preview_substeps(frames=64, substeps=3, preview_frames=16) == 12
    assert preview_substeps(frames=50, substeps=3, preview_frames=16) == 10  # 9.375 rounds up
    assert preview_substeps(frames=8, substeps=1, preview_frames=16) == 1  # never below one


def test_settings_toml_loads_back_to_the_same_recipe(tmp_path):
    recipe = load_recipe(write(tmp_path, MINIMAL), preview=True)
    text = recipe_to_toml(recipe, derive(recipe), device="cpu")
    reloaded = parse_recipe(tomllib.loads(text))
    assert reloaded == recipe
