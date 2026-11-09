"""The Sheet tab: a sheet folder loads as `plume run` wrote it, the card sits on the sheet's crop at Home and
shows the contact sheet's composite, and folders without one sheet are refused."""

import json
import shutil

import numpy as np
import pytest
from PIL import Image

from plume.cli.main import EXIT_OK, main
from plume.recipe.load import load_recipe
from plume.report.composite import sheet_look
from plume.report.contact import composited_image
from plume.view.navigation import Navigation
from plume.view.sheet_player import (SheetFolderError, SheetSource, card_home, cut_frames, find_sheet,
                                     home_rectangle, sheet_background, sheet_image)
from support.tiny import TINY

BACKGROUND = "#6a7a5a"


@pytest.fixture(scope="module")
def sheet_folder(tmp_path_factory):
    folder = tmp_path_factory.mktemp("sheet")
    recipe = folder / "puff.toml"
    recipe.write_text(TINY)
    assert main(["run", str(recipe), "--device", "cpu", "--out", str(folder / "out")]) == EXIT_OK
    return folder / "out"


def test_a_folder_loads_the_sheet_plume_run_wrote(sheet_folder):
    source = SheetSource.from_folder(sheet_folder)
    info = json.loads((sheet_folder / "puff.json").read_text())
    assert source.name == "puff" and len(source.frames) == info["frames"] == 4
    assert source.frame_m == pytest.approx(info["frame_m"]) and source.fps == pytest.approx(info["fps"])
    assert source.look_note is None and source.recipe is not None
    assert source.steps_per_frame is not None and len(source.steps_per_frame) == 4
    sheet = np.asarray(Image.open(sheet_folder / "puff.png").convert("RGBA"))
    assert np.array_equal(source.frames[1], sheet[0:64, 64:128])
    recipe = load_recipe(sheet_folder / "settings.toml")
    expected = composited_image(source.frames[2], BACKGROUND, sheet_look(recipe))
    assert np.array_equal(np.asarray(source.card(2, BACKGROUND)), np.asarray(expected))


def test_without_settings_the_default_look_is_used_and_said(sheet_folder, tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    for name in ("puff.png", "puff.json"):
        shutil.copy(sheet_folder / name, bare / name)
    source = SheetSource.from_folder(bare)
    assert source.recipe is None and "default look" in source.look_note


def test_folders_without_exactly_one_sheet_are_refused(sheet_folder, tmp_path):
    with pytest.raises(SheetFolderError, match="holds no sheet"):
        find_sheet(tmp_path)
    two = tmp_path / "two"
    shutil.copytree(sheet_folder, two)
    shutil.copy(two / "puff.png", two / "other.png")
    shutil.copy(two / "puff.json", two / "other.json")
    with pytest.raises(SheetFolderError, match="2 sheets"):
        find_sheet(two)
    (tmp_path / "half.json").write_text('{"frames": 4}')
    Image.new("RGBA", (8, 8)).save(tmp_path / "half.png")
    with pytest.raises(SheetFolderError, match="not a sheet's JSON"):
        SheetSource.from_folder(tmp_path)


def test_cut_frames_refuses_a_sheet_too_small():
    with pytest.raises(SheetFolderError, match="too small"):
        cut_frames(np.zeros((64, 64, 4), dtype=np.uint8), 4, 2, 64)


def test_at_home_the_card_covers_the_sheets_crop(cpu_device):
    from plume.recipe.derived import derive
    from plume.view.live_run import LiveRun
    from support.recipes import tiny_recipe

    recipe = tiny_recipe(emitter=[{"name": "puff", "center_m": [0.1, 0.3, 0.0], "radius_m": 0.2, "end_s": 0.5,
                                   "smoke_per_s": 5.0}], camera={"elevation_deg": 20.0, "azimuth_deg": 30.0})
    derived = derive(recipe)
    run = LiveRun(recipe, derived, "cpu", budget_bytes=1e9)
    while run.advance() is not None:
        pass
    run.wait_for_assembly()
    source = SheetSource.from_assembly(run.assembled, recipe, derived.fps)
    nav = Navigation(derived.domain_min_m, derived.size_m)
    nav.set_viewport(300, 200)
    center, half = home_rectangle(run.view, run.assembled)
    nav.home(recipe.camera.elevation_deg, recipe.camera.azimuth_deg, center, half)
    left, top, side = source.card_rectangle(nav.view_camera())
    assert side == pytest.approx(200.0)  # the crop is square and fills the viewport's height
    assert left == pytest.approx(50.0) and top == pytest.approx(0.0, abs=1e-6)


def test_the_tab_image_is_the_background_with_the_card_scaled_in(sheet_folder):
    source = SheetSource.from_folder(sheet_folder)
    nav = Navigation((-0.5, -0.5, -0.5), (1.0, 1.0, 1.0))
    nav.set_viewport(256, 128)
    center, half = card_home(source)
    nav.home(0.0, 0.0, center, half)
    card = source.card(1, BACKGROUND)
    image = sheet_image(source, card, nav.view_camera(), BACKGROUND)
    assert image.shape == (128, 256, 4)
    background = sheet_background(BACKGROUND)[0, 0]
    assert np.array_equal(image[:, :64], np.broadcast_to(background, (128, 64, 4)))  # left of the card
    inside = image[:, 64:192, :3]
    assert np.array_equal(inside, np.asarray(card.resize((128, 128), Image.Resampling.BILINEAR,
                                                         box=(0.0, 0.0, 64.0, 64.0))))


def test_a_card_behind_the_eye_draws_only_the_background(sheet_folder):
    source = SheetSource.from_folder(sheet_folder)
    nav = Navigation((-0.5, -0.5, -0.5), (1.0, 1.0, 1.0))
    nav.set_viewport(64, 64)
    nav.toggle_perspective()
    nav.pivot = nav.pivot - nav.basis()[2] * (nav.distance + 5.0)  # the eye passes the card
    assert source.card_rectangle(nav.view_camera()) is None
    image = sheet_image(source, source.card(0, BACKGROUND), nav.view_camera(), BACKGROUND)
    assert np.all(image == sheet_background(BACKGROUND)[0, 0])


def test_a_card_whose_rounded_edges_pass_its_own_draws(sheet_folder):
    source = SheetSource.from_folder(sheet_folder)
    nav = Navigation((-0.5, -0.5, -0.5), (1.0, 1.0, 1.0))
    nav.set_viewport(301, 157)
    center, half = card_home(source)
    nav.home(0.0, 0.0, center, half)
    nav.wheel(0.37)  # a card side of no whole number of pixels
    image = sheet_image(source, source.card(0, BACKGROUND), nav.view_camera(), BACKGROUND)
    assert image.shape == (157, 301, 4)
