from plume.cli.main import main


def test_version_prints_name_and_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == "plume 0.1.0"
