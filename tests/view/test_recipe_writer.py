"""Section 9's recipe writer tests: Save writes only the edited keys and keeps everything else."""

from pathlib import Path

import pytest

from plume.recipe.errors import RecipeError
from plume.recipe.load import load_recipe
from plume.recipe.variation import read_toml, resolve_extends
from plume.view.recipe_writer import COPIED_EMITTERS, write_edits
from support.tiny import TINY

REPO = Path(__file__).resolve().parents[2]

COMMENTED = """# A commented recipe.
seed = 3   # the seed

[domain]
size_m = [1.0, 1.5, 1.0]
cell_m = 0.0625              # 16 x 24 x 16 cells

[time]
duration_s = 1.0
frames = 4

[[emitter]]
name = "puff"
center_m = [0.0, 0.3, 0.0]
radius_m = 0.2               # the radius
end_s = 0.3
smoke_per_s = 6.0
noise = { scale_m = 0.1, strength = 0.5 }

# Forces follow.
[forces]
drag_per_s = 0.5             # keeps it calm
"""

CHILD = '''# a child recipe
extends = "parent.toml"

[dissipation]
smoke_per_s = 0.5
'''


def save(path: Path, edits: dict) -> list[str]:
    merged, _ = resolve_extends(read_toml(path), path)
    return write_edits(path, edits, merged)


def test_an_edit_changes_only_its_value_and_keeps_comments_blank_lines_and_order(tmp_path):
    path = tmp_path / "r.toml"
    path.write_text(COMMENTED)
    save(path, {"domain.cell_m": 0.05, "forces.drag_per_s": 0.75, "seed": 9})
    expected = (COMMENTED.replace("cell_m = 0.0625 ", "cell_m = 0.05   ")
                .replace("drag_per_s = 0.5 ", "drag_per_s = 0.75")
                .replace("seed = 3 ", "seed = 9 "))
    assert path.read_text() == expected


def test_an_emitter_is_found_by_name_and_its_inline_table_key_is_set(tmp_path):
    path = tmp_path / "r.toml"
    path.write_text(COMMENTED)
    save(path, {"emitter.puff.noise.strength": 0.25, "emitter.puff.radius_m": 0.3})
    text = path.read_text()
    assert "noise = { scale_m = 0.1, strength = 0.25 }" in text
    assert "radius_m = 0.3               # the radius" in text
    recipe = load_recipe(path)
    assert recipe.emitter[0].noise.strength == 0.25 and recipe.emitter[0].radius_m == 0.3


def test_a_missing_key_and_table_are_added_and_load_to_the_edited_values(tmp_path):
    path = tmp_path / "r.toml"
    path.write_text(COMMENTED)
    save(path, {"render.light_dir": [0.0, 1.0, 0.0], "forces.turbulence.strength_mps2": 0.1,
                "domain.faces.top": "closed", "look.backgrounds.grass": "#000000"})
    recipe = load_recipe(path)
    assert recipe.render.light_dir == (0.0, 1.0, 0.0)
    assert recipe.forces.turbulence.strength_mps2 == 0.1
    assert recipe.domain.faces.top == "closed"
    assert recipe.look.backgrounds.grass == "#000000"
    text = path.read_text()
    assert "[domain]\nsize_m = [1.0, 1.5, 1.0]\ncell_m = 0.0625              # 16 x 24 x 16 cells\n" in text
    assert 'faces = { top = "closed" }' in text and "turbulence = { strength_mps2 = 0.1 }" in text
    assert text.endswith('[render]\nlight_dir = [0.0, 1.0, 0.0]\n\n[look]\nbackgrounds = { grass = "#000000" }\n')


def test_a_key_from_a_parent_is_written_into_the_child_never_the_parent(tmp_path):
    (tmp_path / "parent.toml").write_text(TINY)
    child = tmp_path / "child.toml"
    child.write_text(CHILD)
    notes = save(child, {"forces.drag_per_s": 0.4, "domain.cell_m": 0.05})
    assert notes == []
    assert (tmp_path / "parent.toml").read_text() == TINY
    assert child.read_text().startswith(CHILD)
    recipe = load_recipe(child)
    assert recipe.forces.drag_per_s == 0.4 and recipe.domain.cell_m == 0.05
    assert recipe.domain.size_m == (1.0, 1.5, 1.0)  # the parent's other [domain] keys still merge in


def test_an_emitter_key_in_a_child_without_emitters_copies_the_parents_list(tmp_path):
    (tmp_path / "parent.toml").write_text(TINY)
    child = tmp_path / "child.toml"
    child.write_text(CHILD)
    before = load_recipe(child)
    notes = save(child, {"emitter.puff.radius_m": 0.25})
    assert notes == [COPIED_EMITTERS]
    assert (tmp_path / "parent.toml").read_text() == TINY
    after = load_recipe(child)
    assert after.emitter[0].radius_m == 0.25
    assert after.emitter[0].noise == before.emitter[0].noise
    assert after.emitter[0].center_m == before.emitter[0].center_m


def test_no_edits_changes_no_byte(tmp_path):
    path = tmp_path / "r.toml"
    path.write_bytes(COMMENTED.encode())
    stamp = path.stat().st_mtime_ns
    assert save(path, {}) == []
    assert path.read_bytes() == COMMENTED.encode() and path.stat().st_mtime_ns == stamp


def test_windows_line_endings_stay(tmp_path):
    path = tmp_path / "r.toml"
    path.write_bytes(COMMENTED.replace("\n", "\r\n").encode())
    save(path, {"forces.drag_per_s": 0.75, "render.soften_px": 1.0})
    data = path.read_bytes()
    assert b"drag_per_s = 0.75" in data
    assert data.count(b"\n") == data.count(b"\r\n")
    assert load_recipe(path).render.soften_px == 1.0


def test_an_unknown_emitter_is_refused_and_the_file_is_untouched(tmp_path):
    path = tmp_path / "r.toml"
    path.write_text(COMMENTED)
    with pytest.raises(RecipeError, match="no emitter is named 'ember'"):
        save(path, {"emitter.ember.radius_m": 0.1})
    assert path.read_text() == COMMENTED


def test_the_example_recipe_round_trips(tmp_path):
    original = (REPO / "recipes" / "smoke_puff.toml").read_text()
    path = tmp_path / "smoke_puff.toml"
    path.write_text(original)
    save(path, {"forces.turbulence.strength_mps2": 0.2, "render.opacity_per_density": 5.0,
                "emitter.puff.velocity_mps": [0.0, 0.5, 0.0]})
    text = path.read_text()
    assert "turbulence = { scale_m = 0.2, strength_mps2 = 0.2, speed_mps = 0.2 }" in text
    assert "opacity_per_density = 5.0" in text
    assert "velocity_mps = [0.0, 0.5, 0.0]" in text
    assert "vorticity_confinement = 3.0  # keeps the curls the grid would smear" in text
    assert len(text.splitlines()) == len(original.splitlines())
    recipe = load_recipe(path)
    assert recipe.render.opacity_per_density == 5.0 and recipe.emitter[0].velocity_mps == (0.0, 0.5, 0.0)


def test_a_save_keeps_the_files_permissions_and_a_symlink(tmp_path):
    target = tmp_path / "real.toml"
    target.write_text(COMMENTED)
    target.chmod(0o644)
    mode = target.stat().st_mode  # read back: Windows keeps only the read-only bit, so 0o644 reads as 0o666
    link = tmp_path / "link.toml"
    link.symlink_to(target)
    save(link, {"seed": 4})
    assert link.is_symlink() and load_recipe(target).seed == 4
    assert target.stat().st_mode == mode


def test_a_file_that_is_not_valid_toml_is_refused(tmp_path):
    path = tmp_path / "r.toml"
    path.write_text("seed = = 3\n")
    with pytest.raises(RecipeError, match="is not valid TOML"):
        write_edits(path, {"seed": 4}, {})
    assert path.read_text() == "seed = = 3\n"
