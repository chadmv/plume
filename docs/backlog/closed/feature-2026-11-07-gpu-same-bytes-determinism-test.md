---
title: Test that two identical GPU runs give identical bytes
type: feature
status: closed
created: 2026-11-07
priority: high
source: deep roadmap gaps review, 2026-11-07
closed: 2026-11-07
resolution: fixed
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

## Resolution
`tests/cli/test_gpu_same_bytes.py` runs the smoke puff preview twice on CUDA (removing the output folder
between runs), checks that the run used a CUDA device, and compares every file in `preview/` but
`timing.txt` byte for byte. It is `gpu`-marked and skips without CUDA, so Linux CI and cloud sessions
skip it. It passed on the 2080 Ti on 2026-11-07, alongside the CPU against CUDA test.
