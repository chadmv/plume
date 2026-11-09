import numpy as np
import warp as wp

from plume.view.frame_cache import FrameCache, frame_bytes, frame_stride

CELLS = (8, 6, 4)


def field(values, device):
    return wp.array(np.asarray(values, dtype=np.float32), dtype=float, device=device)


def test_a_stored_frame_is_the_field_rounded_to_16_bits(cpu_device):
    rng = np.random.default_rng(5)
    smoke = rng.uniform(0.0, 3.0, CELLS).astype(np.float32)
    temperature = rng.uniform(290.0, 1500.0, CELLS).astype(np.float32)
    cache = FrameCache(CELLS, frames=4, budget_bytes=1e9, device=cpu_device)
    cache.store(0, field(smoke, cpu_device), field(temperature, cpu_device))
    assert np.array_equal(cache.stored_smoke(0).numpy(), smoke.astype(np.float16))
    wide_smoke, wide_temperature = cache.load(0, cache.scratch())
    assert np.array_equal(wide_smoke.numpy(), smoke.astype(np.float16).astype(np.float32))
    assert np.array_equal(wide_temperature.numpy(), temperature.astype(np.float16).astype(np.float32))


def test_the_stride_doubles_until_the_kept_frames_fit():
    one = frame_bytes(CELLS)
    assert one == 2 * 2 * 8 * 6 * 4
    assert frame_stride(64, CELLS, 64 * one) == 1
    assert frame_stride(64, CELLS, 64 * one - 1) == 2
    assert frame_stride(64, CELLS, 16 * one) == 4
    assert frame_stride(64, CELLS, 1) == 64  # one frame is always kept


def test_a_thinned_cache_skips_frames_and_says_so(cpu_device):
    cache = FrameCache(CELLS, frames=8, budget_bytes=4 * frame_bytes(CELLS), device=cpu_device)
    zeros = field(np.zeros(CELLS), cpu_device)
    for frame in range(8):
        cache.store(frame, zeros, zeros)
    assert cache.kept_frames() == [0, 2, 4, 6]
    assert cache.nearest_kept(5) == 4
    assert "every 2nd frame" in cache.thinning_note()
    assert FrameCache(CELLS, frames=8, budget_bytes=1e9, device=cpu_device).thinning_note() is None


def test_nearest_kept_before_anything_lands_is_none(cpu_device):
    assert FrameCache(CELLS, frames=8, budget_bytes=1e9, device=cpu_device).nearest_kept(3) is None
