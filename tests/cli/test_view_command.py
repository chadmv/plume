import sys

import pytest

from plume.cli.main import EXIT_FAILED, EXIT_RECIPE_ERROR, EXIT_USAGE, main
from support.tiny import TINY


def test_view_refuses_a_folder_without_a_sheet(tmp_path, capsys):
    assert main(["view", str(tmp_path)]) == EXIT_USAGE
    assert "holds no sheet" in capsys.readouterr().err


def test_view_of_a_sheet_folder_takes_no_recipe_options(tmp_path, capsys):
    assert main(["view", str(tmp_path), "--preview"]) == EXIT_USAGE
    assert "a sheet folder is shown as it is" in capsys.readouterr().err


def test_view_opens_a_sheet_folder_without_a_device(tmp_path, monkeypatch):
    import plume.view.sheet_app as sheet_app

    recipe = tmp_path / "puff.toml"
    recipe.write_text(TINY)
    assert main(["run", str(recipe), "--device", "cpu", "--out", str(tmp_path / "out")]) == 0
    opened = []
    monkeypatch.setattr(sheet_app, "run_sheet_viewer", lambda folder, source, out: opened.append((folder, source, out)))
    assert main(["view", str(tmp_path / "out"), "--out", str(tmp_path / "clips")]) == 0
    folder, source, out = opened[0]
    assert folder == tmp_path / "out" and source.name == "puff" and out == str(tmp_path / "clips")


def test_view_without_the_extra_names_the_install_command(tmp_path, capsys, monkeypatch):
    path = tmp_path / "puff.toml"
    path.write_text(TINY)
    monkeypatch.setitem(sys.modules, "imgui_bundle", None)  # importing it raises ImportError
    assert main(["view", str(path)]) == EXIT_FAILED
    assert "uv sync --extra view" in capsys.readouterr().err


def test_view_cache_budget_must_be_above_zero(tmp_path, capsys):
    path = tmp_path / "puff.toml"
    path.write_text(TINY)
    with pytest.raises(SystemExit) as raised:
        main(["view", str(path), "--cache-gb", "0"])
    assert raised.value.code == EXIT_USAGE
    assert "must be above 0" in capsys.readouterr().err


def test_a_bad_recipe_exits_2_before_any_window_even_without_the_extra(tmp_path, capsys, monkeypatch):
    path = tmp_path / "bad.toml"
    path.write_text(TINY.replace("cell_m = 0.0625", "cell_m = -1.0"))
    monkeypatch.setitem(sys.modules, "imgui_bundle", None)
    assert main(["view", str(path)]) == EXIT_RECIPE_ERROR
    assert "recipe error" in capsys.readouterr().err
