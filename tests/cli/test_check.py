import pytest

from plume.cli.main import EXIT_OK, EXIT_RECIPE_ERROR, EXIT_USAGE, main

RECIPE = """
[domain]
size_m = [1.0, 2.0, 1.0]
cell_m = 0.05

[time]
duration_s = 2.0

[[emitter]]
name = "puff"
center_m = [0.0, 0.2, 0.0]
radius_m = 0.2
end_s = 0.5
"""


def test_check_prints_grid_and_resolved_settings(tmp_path, capsys):
    path = tmp_path / "puff.toml"
    path.write_text(RECIPE)
    assert main(["check", str(path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "grid 20 x 40 x 20 cells" in out
    assert 'name = "puff"' in out
    assert "[resolved]" in out


def test_check_reports_recipe_errors_with_exit_code_2(tmp_path, capsys):
    path = tmp_path / "bad.toml"
    path.write_text(RECIPE.replace("cell_m", "cel_m"))
    assert main(["check", str(path)]) == EXIT_RECIPE_ERROR
    assert "did you mean cell_m" in capsys.readouterr().err


def test_check_reports_a_set_nan_as_a_recipe_error(tmp_path, capsys):
    path = tmp_path / "puff.toml"
    path.write_text(RECIPE)
    assert main(["check", str(path), "--set", "emitter.puff.smoke_per_s=nan"]) == EXIT_RECIPE_ERROR
    assert "smoke_per_s must be a finite number" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["check", "puff.toml", "--bad-flag"], ["chekc", "puff.toml"], ["run"]])
def test_usage_errors_exit_apart_from_recipe_errors(argv, capsys):
    with pytest.raises(SystemExit) as raised:
        main(argv)
    assert raised.value.code == EXIT_USAGE != EXIT_RECIPE_ERROR
    assert "usage:" in capsys.readouterr().err
