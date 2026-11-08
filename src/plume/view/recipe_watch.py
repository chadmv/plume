"""Following the opened recipe on disk: it and every parent in its `extends` chain are polled four times a
second for a changed modification time or size (no file-watcher dependency)."""

import time
from pathlib import Path

POLL_S = 0.25


def chain_paths(recipe_path: Path, extends_chain: tuple[str, ...]) -> list[Path]:
    """The recipe and its parents as files: each parent is named relative to the file that extends it."""
    paths = [recipe_path]
    for parent in extends_chain:
        paths.append(paths[-1].parent / parent)
    return paths


class RecipeWatch:
    """Remembers the files' stamps and reports when any of them changes."""

    def __init__(self, paths: list[Path]):
        self.paths = list(paths)
        self._stamps = self._read()
        self._last_poll_s = time.perf_counter()

    def follow(self, paths: list[Path]) -> None:
        """Watches a new set of files (after a reload changed the `extends` chain), as they are now."""
        self.paths = list(paths)
        self._stamps = self._read()

    def changed(self, now_s: float | None = None) -> bool:
        """True once per change, checking at most every POLL_S seconds of `now_s` (perf_counter time)."""
        now_s = time.perf_counter() if now_s is None else now_s
        if now_s - self._last_poll_s < POLL_S:
            return False
        self._last_poll_s = now_s
        stamps = self._read()
        if stamps == self._stamps:
            return False
        self._stamps = stamps
        return True

    def _read(self) -> list[tuple[int, int] | None]:
        stamps = []
        for path in self.paths:
            try:
                status = path.stat()
                stamps.append((status.st_mtime_ns, status.st_size))
            except OSError:
                stamps.append(None)  # missing for now; its return is a change
        return stamps
