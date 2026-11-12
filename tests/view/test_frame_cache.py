import numpy as np
import warp as wp

from plume.view.frame_cache import FrameCache, frame_bytes, frame_stride, keeps_velocity

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


def test_velocity_is_dropped_before_any_frame():
    with_velocity = frame_bytes(CELLS, velocity=True)
    assert with_velocity == 5 * 2 * 8 * 6 * 4
    assert keeps_velocity(8, CELLS, 8 * with_velocity)
    assert not keeps_velocity(8, CELLS, 8 * with_velocity - 1)
    cache = FrameCache(CELLS, frames=8, budget_bytes=8 * with_velocity - 1, device="cpu")
    assert not cache.has_velocity and cache.stride == 1 and not cache.thinned
    assert "no velocity" in cache.thinning_note() and "every" not in cache.thinning_note()
    assert FrameCache(CELLS, frames=8, budget_bytes=8 * with_velocity, device="cpu").has_velocity


def test_a_kept_velocity_is_the_centered_velocity_rounded_to_16_bits(cpu_device):
    rng = np.random.default_rng(7)
    nx, ny, nz = CELLS
    u = rng.uniform(-2.0, 2.0, (nx + 1, ny, nz)).astype(np.float32)
    v = rng.uniform(-2.0, 2.0, (nx, ny + 1, nz)).astype(np.float32)
    w = rng.uniform(-2.0, 2.0, (nx, ny, nz + 1)).astype(np.float32)
    zeros = field(np.zeros(CELLS), cpu_device)
    cache = FrameCache(CELLS, frames=2, budget_bytes=1e9, device=cpu_device)
    cache.store(0, zeros, zeros, (field(u, cpu_device), field(v, cpu_device), field(w, cpu_device)))
    centered = np.stack([0.5 * (u[:-1] + u[1:]), 0.5 * (v[:, :-1] + v[:, 1:]), 0.5 * (w[:, :, :-1] + w[:, :, 1:])],
                        axis=-1).astype(np.float32)
    assert cache.velocity_kept(0)
    assert np.array_equal(cache.load_velocity(0, cache.velocity_scratch()).numpy(),
                          centered.astype(np.float16).astype(np.float32))
    assert cache.stored_bytes == frame_bytes(CELLS, velocity=True)


def test_a_thinned_cache_skips_frames_and_says_so(cpu_device):
    cache = FrameCache(CELLS, frames=8, budget_bytes=4 * frame_bytes(CELLS), device=cpu_device)
    zeros = field(np.zeros(CELLS), cpu_device)
    for frame in range(8):
        cache.store(frame, zeros, zeros)
    assert cache.kept_frames() == [0, 2, 4, 6]
    assert cache.nearest_kept(5) == 4
    assert not cache.has_velocity
    assert "every 2nd frame and no velocity" in cache.thinning_note()
    assert FrameCache(CELLS, frames=8, budget_bytes=1e9, device=cpu_device).thinning_note() is None


def test_nearest_kept_before_anything_lands_is_none(cpu_device):
    assert FrameCache(CELLS, frames=8, budget_bytes=1e9, device=cpu_device).nearest_kept(3) is None
