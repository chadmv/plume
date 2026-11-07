import json

import numpy as np
import pytest

from plume.render.camera import make_camera, make_domain_view
from plume.render.raw_frame import CHANNELS, HEAT, NORMAL_X, NORMAL_Y, NORMAL_Z, THICKNESS
from plume.sheet.assemble import assemble
from plume.sheet.crop import NothingVisibleError
from plume.sheet.pack import pack
from plume.sheet.quantize import quantize
from plume.sheet.sheet_json import SheetInfo, sheet_json_text, source_path

VIEW = make_domain_view(make_camera(0.0, 0.0), (-1.0, 0.0, -1.0), (2.0, 2.0, 2.0), 0.0625, 2.0)  # 64 px


def raw_disc(center, radius, heat=0.0):
    frame = np.zeros((64, 64, CHANNELS), dtype=np.float32)
    frame[..., NORMAL_Z] = 1.0
    ys, xs = np.mgrid[0:64, 0:64] + 0.5
    inside = (xs - center[0]) ** 2 + (ys - center[1]) ** 2 < radius**2
    frame[inside, THICKNESS] = 0.8
    frame[inside, HEAT] = heat
    return frame


def frames_rising():
    return [raw_disc((32, 50 - 8 * i), 6 + 2 * i, heat=10.0 / (i + 1)) for i in range(4)]


def test_crop_is_square_and_every_frame_keeps_an_empty_gutter():
    result = assemble(frames_rising(), VIEW, np.array([0.0, 0.2, 0.0]), 64, soften_px=0.75, margin=0.04)
    for frame in result.frames:
        assert frame.shape == (64, 64, 4)
        assert not frame[:2, :, :2].any() and not frame[-2:, :, :2].any()
        assert not frame[:, :2, :2].any() and not frame[:, -2:, :2].any()


def test_heat_is_normalized_to_the_hottest_frame():
    result = assemble(frames_rising(), VIEW, np.array([0.0, 0.2, 0.0]), 64, soften_px=0.75, margin=0.04)
    assert max(int(frame[..., 0].max()) for frame in result.frames) == 255
    assert result.frames[0][..., 0].max() > result.frames[3][..., 0].max()


def test_frame_m_and_seat_follow_the_crop():
    result = assemble(frames_rising(), VIEW, np.array([0.0, 0.0, 0.0]), 64, soften_px=0.0, margin=0.0)
    left, top, right, bottom = result.crop.box()
    assert right - left == pytest.approx(bottom - top)
    assert result.frame_m == pytest.approx(result.crop.side * VIEW.pixel_m)
    seat_x, seat_y = result.seat
    assert seat_x == pytest.approx(0.5, abs=0.02)  # the content is centered on x = 0
    assert seat_y > 1.0  # the floor (y = 0) is below the content


def test_nothing_visible_is_an_error():
    empty = np.zeros((64, 64, CHANNELS), dtype=np.float32)
    with pytest.raises(NothingVisibleError):
        assemble([empty], VIEW, np.zeros(3), 64, soften_px=0.75, margin=0.04)


def test_quantize_encodes_normals_with_y_up():
    frame = np.zeros((2, 2, CHANNELS))
    frame[..., THICKNESS] = 0.5
    frame[0, 0, NORMAL_Z] = 1.0  # facing the camera
    frame[0, 1, NORMAL_Y] = 1.0  # facing up
    frame[1, 0, NORMAL_X] = -1.0  # facing left
    frame[1, 1, NORMAL_Z] = 1.0
    frame[1, 1, THICKNESS] = 0.0  # empty
    rgba = quantize(frame, heat_divisor=0.0)
    assert tuple(rgba[0, 0, 2:]) == (128, 128)
    assert rgba[0, 1, 3] == 255
    assert rgba[1, 0, 2] == 0
    assert tuple(rgba[1, 1]) == (0, 0, 128, 128)
    assert rgba[0, 0, 1] == 128  # 0.5 * 255 rounds half up


def test_pack_fills_rows_left_to_right_and_leaves_unused_slots_zero():
    frames = [np.full((4, 4, 4), index + 1, dtype=np.uint8) for index in range(5)]
    sheet = pack(frames, columns=3)
    assert sheet.shape == (8, 12, 4)
    assert sheet[0, 4, 0] == 2 and sheet[4, 0, 0] == 4
    assert not sheet[4:, 8:].any()


def test_json_keys_are_the_contract_in_order(tmp_path):
    info = SheetInfo(frames=64, columns=8, frame_px=256, fps=20.0, frame_m=1.23456789, seat=(0.5, 0.875),
                     source="recipes/smoke_puff.toml", tool="plume 0.1.0",
                     written_by="plume run recipes/smoke_puff.toml")
    text = sheet_json_text(info)
    table = json.loads(text)
    assert list(table) == ["frames", "columns", "frame_px", "fps", "frame_m", "seat", "channels", "source",
                           "tool", "written_by"]
    assert table["frame_m"] == 1.234568
    assert table["channels"] == "heat,thickness,normal_x,normal_y"
    assert text.endswith("}\n")


def test_source_is_relative_to_the_git_root(tmp_path):
    (tmp_path / ".git").mkdir()
    recipe = tmp_path / "effects" / "fire.toml"
    recipe.parent.mkdir()
    recipe.write_text("")
    assert source_path(recipe) == "effects/fire.toml"
