import sys

import pytest

from plume.cli.main import EXIT_FAILED, EXIT_USAGE, main
from support.tiny import TINY


def test_view_refuses_a_folder_until_the_sheet_tab_exists(tmp_path, capsys):
    assert main(["view", str(tmp_path)]) == EXIT_USAGE
    assert "Sheet tab" in capsys.readouterr().err


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
