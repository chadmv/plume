"""Wall-clock timing per stage: the one output excluded from the same-bytes promise."""

import time
from contextlib import contextmanager


class StageTimer:
    """Records how long each named stage takes, in the order stages ran."""

    def __init__(self):
        self.seconds: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.seconds[name] = self.seconds.get(name, 0.0) + time.perf_counter() - start

    def total(self) -> float:
        return sum(self.seconds.values())

    def text(self) -> str:
        lines = [f"{name:<12}{seconds:9.3f} s" for name, seconds in self.seconds.items()]
        lines.append(f"{'total':<12}{self.total():9.3f} s")
        return "\n".join(lines) + "\n"
