"""Shared test fixtures: the CPU device every solver test runs on, and an optional CUDA device."""

import pytest


@pytest.fixture(scope="session")
def cpu_device() -> str:
    from plume.sim.device import init_device

    return init_device("cpu")


@pytest.fixture(scope="session")
def cuda_device() -> str:
    import warp as wp

    from plume.sim.device import init_device

    init_device("cpu")
    if not wp.is_cuda_available():
        pytest.skip("no CUDA GPU")
    return init_device("cuda")
