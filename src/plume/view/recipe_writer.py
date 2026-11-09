"""Save (V14): writes the viewer's edits into the opened recipe with tomlkit, keeping its comments, blank
lines, key order and line endings, and touching no key it was not asked to.

An edit is a dotted key path in `--set`'s grammar (`forces.drag_per_s`, `emitter.puff.noise.strength`) and a
TOML value. A replaced value keeps its trailing comment in the same column. A key the opened recipe does not
hold is added to it, creating its table if needed (a missing top-level table as a `[table]` at the end, a
missing table inside one as an inline table, the style the example recipes use), even when
the value came from an `extends` parent: the parent may be shared, so it is never written. Lists replace
whole in `extends` merging, so an emitter key in a child with no `[[emitter]]` of its own first copies the
parent's emitter list into the child.
"""

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.items import AoT, InlineTable, Table

from plume.recipe.errors import RecipeError

COPIED_EMITTERS = "copied the parent's [[emitter]] list into the recipe (lists replace whole in extends)"


def write_edits(path: Path, edits: dict[str, Any], merged: dict) -> list[str]:
    """Writes `edits` into the recipe at `path`; `merged` is the recipe's table merged with its parents (for
    a parent's emitters). Returns notes for the status line. Writes nothing when `edits` is empty. Raises
    RecipeError when the file cannot be read or a key cannot be placed."""
    if not edits:
        return []
    try:
        with path.open(encoding="utf-8", newline="") as file:
            text = file.read()
    except (OSError, UnicodeDecodeError) as error:
        raise RecipeError(f"cannot read {path} to save it: {error}") from None
    document = tomlkit.parse(text)
    notes: list[str] = []
    for key, value in edits.items():
        parts = key.split(".")
        if parts[0] == "emitter":
            if len(parts) < 3:
                raise RecipeError(f"cannot save {key}: name the emitter, as emitter.<name>.<key>")
            target = _emitter(document, parts[1], merged, notes)
            _set(target, parts[2:], value, key)
        else:
            _set(document, parts, value, key)
    saved = tomlkit.dumps(document)
    if "\r\n" in text and not re.search(r"(?<!\r)\n", text):
        saved = re.sub(r"(?<!\r)\n", "\r\n", saved)  # lines tomlkit added follow the file's line endings
    _write(path, saved)
    return notes


def _emitter(document, name: str, merged: dict, notes: list[str]) -> Table:
    if "emitter" not in document:
        copied = tomlkit.aot()
        for emitter in merged.get("emitter", []):
            copied.append(_table(emitter))
        document.append("emitter", copied)
        notes.append(COPIED_EMITTERS)
    emitters = document["emitter"]
    if not isinstance(emitters, AoT):
        raise RecipeError("cannot save an emitter key: emitter in the recipe is not a [[emitter]] list")
    for emitter in emitters:
        if emitter.get("name") == name:
            return emitter
    raise RecipeError(f"cannot save emitter.{name}: no emitter is named {name!r}")


def _set(container, parts: list[str], value: Any, key: str) -> None:
    for depth, part in enumerate(parts[:-1]):
        child = container.get(part)
        if child is None:
            if not isinstance(container, TOMLDocument):
                container[part] = _inline_table(parts[depth + 1:], value)
                return
            child = tomlkit.table()
            container[part] = child
        elif not isinstance(child, (Table, InlineTable)):
            raise RecipeError(f"cannot save {key}: {'.'.join(parts[:depth + 1])} is a value, not a table")
        container = child
    leaf = parts[-1]
    old = container.get(leaf)
    item = tomlkit.item(value)
    if old is not None and hasattr(old, "trivia") and hasattr(item, "trivia") and old.trivia.comment:
        # keep the comment where it was: the gap shrinks or grows by the value's change in length
        gap = len(old.trivia.comment_ws) + len(old.as_string()) - len(item.as_string())
        item.trivia.comment_ws = " " * max(gap, 1)
        item.trivia.comment = old.trivia.comment
    container[leaf] = item


def _inline_table(parts: list[str], value: Any) -> InlineTable:
    """`{ a = { b = value } }` for parts [a, b]."""
    nested = value
    for part in reversed(parts):
        nested = {part: nested}
    return _inline(nested)


def _inline(values: dict) -> InlineTable:
    """An inline table spaced as the example recipes write them (`{ a = 1, b = 2 }`)."""
    return tomlkit.parse(f"value = {_inline_text(values)}\n")["value"]


def _inline_text(values: dict) -> str:
    pairs = (f"{key} = {_inline_text(value) if isinstance(value, dict) else tomlkit.item(value).as_string()}"
             for key, value in values.items())
    return "{ " + ", ".join(pairs) + " }"


def _table(values: dict) -> Table:
    table = tomlkit.table()
    for key, value in values.items():
        table[key] = _inline(value) if isinstance(value, dict) else value
    return table


def _write(path: Path, text: str) -> None:
    """Writes through a temporary file beside the recipe and a replace, so a failed write never leaves half a
    recipe."""
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as file:
            file.write(text)
        os.replace(temporary, path)
    except OSError as error:
        Path(temporary).unlink(missing_ok=True)
        raise RecipeError(f"cannot save {path}: {error.strerror or error}") from None
