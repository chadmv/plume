"""Clips and stills: names count up, a clip holds one image per frame at 1 / fps, and the `.toml` beside it
reads back to the same camera."""

import numpy as np
import pytest
from PIL import Image

from plume.view.capture import capture_folder, next_counter, read_capture, write_clip, write_still
from plume.view.navigation import Navigation


def images(count, size=(6, 8)):
    return [np.full((*size, 4), 20 * index, dtype=np.uint8) for index in range(count)]


def test_the_folder_is_out_then_the_recipes_then_the_sheets(tmp_path):
    assert capture_folder("somewhere", "puff", None).as_posix() == "somewhere/view"
    assert capture_folder(None, "puff", None).as_posix() == "out/puff/view"
    assert capture_folder(None, None, tmp_path) == tmp_path / "view"


def test_names_count_up_across_stills_and_clips(tmp_path):
    folder = tmp_path / "view"
    assert next_counter(folder, "puff") == 1
    first = write_still(folder, "puff", 7, images(1)[0], {"view": {"frame": 7}})
    assert first.name == "puff-f007-001.png"
    clip = write_clip(folder, "puff", images(3), 24.0, {"view": {"frames": [0, 1, 2]}})
    assert clip.name == "puff-clip-002.png"
    (folder / "puffy-f001-009.png").write_bytes(b"")  # another name's counter does not count
    assert write_still(folder, "puff", 0, images(1)[0], {}).name == "puff-f000-003.png"


def test_a_clip_has_one_image_per_frame_shown_one_over_fps(tmp_path):
    frames = images(5)
    path = write_clip(tmp_path, "puff", frames, 24.0, {"view": {"frames": list(range(5))}})
    with Image.open(path) as clip:
        assert clip.n_frames == 5
        for index in range(5):
            clip.seek(index)
            assert clip.info["duration"] == pytest.approx(1000.0 / 24.0, abs=0.5)
            assert np.array_equal(np.asarray(clip.convert("RGBA")), frames[index])


def test_the_toml_reloads_to_the_same_camera(tmp_path):
    nav = Navigation((-0.5, 0.0, -0.5), (1.0, 1.5, 1.0))
    nav.set_viewport(320, 200)
    nav.tumble(40.0, -25.0)
    nav.toggle_perspective()
    nav.wheel(2.0)
    path = write_still(tmp_path, "puff", 3, images(1)[0], {"view": {"frame": 3, "tab": "volume"},
                                                           "camera": nav.pose_table()})
    read = read_capture(path)
    assert read["view"] == {"frame": 3, "tab": "volume"}
    again = Navigation((-0.5, 0.0, -0.5), (1.0, 1.5, 1.0))
    again.set_viewport(320, 200)
    again.set_pose(read["camera"])
    assert again.pose() == nav.pose()
    camera, camera_again = nav.view_camera(), again.view_camera()
    assert np.allclose(camera.eye, camera_again.eye) and camera.pixel == pytest.approx(camera_again.pixel)
