"""The channel layout and shade keys: which strings a recipe may choose, and the moved light direction."""

import pytest

from plume.cli.main import EXIT_RECIPE_ERROR, main
from plume.recipe.errors import RecipeError
from plume.recipe.load import parse_recipe
from plume.recipe.schema import NORMAL_LAYOUT, SHADE_LAYOUT
from support.recipes import recipe_table


def test_shade_is_the_default_layout():
    assert parse_recipe(recipe_table()).output.channels == SHADE_LAYOUT


@pytest.mark.parametrize("layout", [SHADE_LAYOUT, NORMAL_LAYOUT])
def test_each_layout_is_accepted(layout):
    assert parse_recipe(recipe_table(output={"channels": layout})).output.channels == layout


def test_another_layout_is_a_recipe_error_naming_the_valid_ones(tmp_path, capsys):
    path = tmp_path / "bad.toml"
    path.write_text('[domain]\nsize_m = [1.0, 1.0, 1.0]\ncell_m = 0.1\n[time]\nduration_s = 1.0\n'
                    '[[emitter]]\nname = "puff"\ncenter_m = [0.0, 0.3, 0.0]\nradius_m = 0.2\nend_s = 0.5\n'
                    '[output]\nchannels = "heat,thickness,shade"\n')
    assert main(["check", str(path)]) == EXIT_RECIPE_ERROR
    error = capsys.readouterr().err
    assert SHADE_LAYOUT in error and NORMAL_LAYOUT in error


def test_look_sun_dir_points_at_render_light_dir():
    with pytest.raises(RecipeError, match=r"look\.sun_dir; it moved to render\.light_dir"):
        parse_recipe(recipe_table(look={"sun_dir": [0.0, 1.0, 0.0]}))


def test_light_dir_must_have_a_direction():
    with pytest.raises(RecipeError, match=r"render\.light_dir"):
        parse_recipe(recipe_table(render={"light_dir": [0.0, 0.0, 0.0]}))


@pytest.mark.parametrize("key, value", [("render", {"shade_fill": 1.5}), ("render", {"shade_fade_thickness": 0.0}),
                                        ("render", {"shade_neighborhood_px": 0.0}), ("look", {"shade_depth": -0.1})])
def test_shade_values_out_of_range_are_rejected(key, value):
    with pytest.raises(RecipeError, match=next(iter(value))):
        parse_recipe(recipe_table(**{key: value}))
