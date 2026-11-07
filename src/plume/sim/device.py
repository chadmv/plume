"""Choosing where kernels run, and the Warp settings every run needs before any kernel loads."""

import warp as wp

DEVICE_CHOICES = ("auto", "cuda", "cpu")


class DeviceError(Exception):
    """The requested device is not available."""


def init_device(choice: str) -> str:
    """Initializes Warp for deterministic runs and returns the Warp device name for `choice`."""
    _configure_warp()
    if choice == "cpu":
        return "cpu"
    if wp.is_cuda_available():
        return "cuda:0"
    if choice == "cuda":
        raise DeviceError("--device cuda was asked for, but no CUDA GPU is available")
    return "cpu"


def _configure_warp() -> None:
    # Deterministic mode must be set before any module is built; it guards scatters (atomics). The solver
    # itself only gathers, so this is a safety net. Backward passes are never used.
    wp.config.deterministic = wp.DeterministicMode.RUN_TO_RUN
    wp.config.enable_backward = False
    wp.config.quiet = True
    wp.init()
