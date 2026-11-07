"""Wall-clock timing per stage: the one output excluded from the same-bytes promise."""

import time
from contextlib import contextmanager


class StageTimer:
    """Records how long each named stage takes, in the order stages ran."""

    def __init__(self):
        self.seconds: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str):
        self.seconds.setdefault(name, 0.0)
        start = time.perf_counter()
        try:
            yield
        finally:
            self.seconds[name] += time.perf_counter() - start

    def exclude(self, outer: str, inner: str) -> None:
        """Removes a nested stage's time from the stage that contained it, so stages never overlap."""
        self.seconds[outer] -= self.seconds.get(inner, 0.0)

    def total(self) -> float:
        return sum(self.seconds.values())

    def text(self) -> str:
        lines = [f"{name:<12}{seconds:9.3f} s" for name, seconds in self.seconds.items()]
        lines.append(f"{'total':<12}{self.total():9.3f} s")
        return "\n".join(lines) + "\n"
