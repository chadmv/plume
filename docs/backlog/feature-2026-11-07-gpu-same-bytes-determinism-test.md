---
title: Test that two identical GPU runs give identical bytes
type: feature
status: open
created: 2026-11-07
priority: high
source: deep roadmap gaps review, 2026-11-07
---

# Test that two identical GPU runs give identical bytes

## Summary
The same-bytes test runs on CPU only and the one `gpu` test compares CPU against CUDA within a tolerance,
so nothing checks that two CUDA runs on the 2080 Ti match byte for byte. That is where nondeterminism
would come from (thread scheduling, atomics), and slice 2's multigrid and vorticity kernels add risk.

## Acceptance / Done When
- A `gpu`-marked test runs the smoke puff preview twice on CUDA and compares every output but
  `timing.txt` byte for byte; it skips without CUDA.

## Related
- `tests/cli/test_run.py:167-174` (`--device cpu` only), `tests/cli/test_cpu_gpu.py:54-66`
- `src/plume/sim/device.py`
- [[feature-2026-11-07-slice-2-solver-quality-iteration-tools]]

## Progress
`tests/cli/test_gpu_same_bytes.py` runs the smoke puff preview twice on CUDA (removing the output folder
between runs), checks that the run really used CUDA, and compares every file in `preview/` but
`timing.txt` byte for byte. It is `gpu`-marked and skips without CUDA, so Linux CI and cloud sessions
skip it; the same test body was checked on CPU in a cloud session. Close this item once it passes on the
2080 Ti.
