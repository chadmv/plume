from plume.cli.main import EXIT_OK, EXIT_RECIPE_ERROR, main

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
