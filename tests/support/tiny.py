"""A tiny recipe that runs end to end in seconds on CPU."""

TINY = """
seed = 3

[domain]
size_m = [1.0, 1.5, 1.0]
cell_m = 0.0625

[time]
duration_s = 1.0
frames = 4

[[emitter]]
name = "puff"
center_m = [0.0, 0.3, 0.0]
radius_m = 0.2
end_s = 0.3
smoke_per_s = 6.0
temperature_k = 500.0
noise = { scale_m = 0.1, strength = 0.5 }

[output]
frame_px = 64
"""
