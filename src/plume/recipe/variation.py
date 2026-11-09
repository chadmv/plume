"""Recipe variations: `extends` (a recipe built on a parent recipe) and `--set key=value` overrides.

Both work on parsed TOML tables before the schema builds them, so every key they bring in is checked by
the same strict build step as a key written in the file.
"""

import copy
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from plume.recipe.errors import RecipeError

MAX_EXTENDS_DEPTH = 8
EMITTER_BY_INDEX = re.compile(r"^emitter\[(\d+)\]$")


@dataclass(frozen=True)
class RecipeOrigin:
    """Where a resolved recipe came from, for the settings log."""

    extends_chain: tuple[str, ...] = ()  # each parent's path as written, nearest parent first
    sets: tuple[str, ...] = ()  # the --set overrides, in order


def read_toml(path: Path) -> dict:
    """Parses a TOML file, turning a missing file or bad TOML into a RecipeError."""
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError:
        raise RecipeError(f"recipe not found: {path}") from None
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise RecipeError(f"{path} is not valid TOML: {error}") from None
    except OSError as error:
        raise RecipeError(f"cannot read {path}: {error.strerror or error}") from None


def resolve_extends(table: dict, path: Path) -> tuple[dict, tuple[str, ...]]:
    """Merges the recipe at `path` (already parsed as `table`) over its parents.

    Returns the merged table, with no `extends` key left, and the chain of parent paths as written.
    """
    chain: list[str] = []
    seen = {path.resolve()}
    merged = dict(table)
    child_path = path
    while True:
        parent_text = merged.pop("extends", "")
        if not isinstance(parent_text, str):
            raise RecipeError(f"extends in {child_path} must be text, got {type(parent_text).__name__}")
        if parent_text == "":
            return merged, tuple(chain)
        check_extends_path(parent_text)
        if len(chain) == MAX_EXTENDS_DEPTH:
            raise RecipeError(f"extends goes deeper than {MAX_EXTENDS_DEPTH} parents, starting at {path}")
        parent_path = child_path.parent / parent_text
        if parent_path.resolve() in seen:
            raise RecipeError(f"extends forms a loop: {child_path} extends {parent_text}, which is already "
                              f"in the chain")
        seen.add(parent_path.resolve())
        chain.append(parent_text)
        parent = read_toml(parent_path)
        # The parent's own `extends` stays in the merged table for the next round; the child's is gone.
        merged = deep_merge(parent, merged)
        child_path = parent_path


def check_extends_path(text: str) -> None:
    """A parent is named relative to its child, so recipes never carry machine-local paths."""
    if PurePosixPath(text).is_absolute() or PureWindowsPath(text).is_absolute() or PureWindowsPath(text).drive:
        raise RecipeError(f"extends must be a path relative to the recipe, got {text!r}")
    if not text.endswith(".toml"):
        raise RecipeError(f"extends must name a .toml recipe, got {text!r}")


def deep_merge(parent: dict, child: dict) -> dict:
    """The child's values over the parent's. Tables merge key by key; anything else, lists included, is
    replaced whole, so a child's [[emitter]] list replaces the parent's."""
    merged = dict(parent)
    for key, value in child.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def apply_sets(table: dict, sets: tuple[str, ...]) -> dict:
    """Applies `--set key=value` overrides to a parsed recipe table, in order.

    Keys are dotted (`forces.drag_per_s`); an emitter is named by its name (`emitter.puff.radius_m`) or
    its index (`emitter[0].radius_m`). The value is read as a TOML value (`0.5`, `[0, 1, 0]`, `"text"`)
    and taken as plain text when it is not one, so `domain.faces.top=closed` works.
    """
    result = copy.deepcopy(table)
    for item in sets:
        key, value = set_item(item)
        _set_value(result, key, value, f"--set {item!r}")
    return result


def set_item(item: str) -> tuple[str, Any]:
    """Parses one `--set key=value` item into its key and TOML value."""
    key, value = _split_set(item)
    if key == "extends":
        raise RecipeError("--set cannot change extends; parents are merged before --set applies. Write "
                          "extends in the recipe instead")
    return key, _parse_value(value)


def apply_values(table: dict, values: dict[str, Any]) -> dict:
    """A copy of a parsed recipe table with each dotted key set to its TOML value, in order, by the key rules
    of `apply_sets` (the viewer's edits)."""
    result = copy.deepcopy(table)
    for key, value in values.items():
        _set_value(result, key, copy.deepcopy(value), f"edit {key}")
    return result


def _split_set(item: str) -> tuple[str, str]:
    key, sep, value = item.partition("=")
    key = key.strip()
    if not sep or not key:
        raise RecipeError(f"--set needs key=value, got {item!r}")
    return key, value.strip()


def _parse_value(text: str) -> Any:
    try:
        return tomllib.loads(f"value = {text}")["value"]
    except tomllib.TOMLDecodeError:
        return text


def _set_value(table: dict, key: str, value: Any, label: str) -> None:
    parts = key.split(".")
    target = table
    index = 0
    while index < len(parts) - 1:
        part = parts[index]
        if part == "emitter" or EMITTER_BY_INDEX.match(part):
            target, index = _emitter_table(table, parts, index, label)
            continue
        child = target.get(part)
        if child is None:
            child = {}
            target[part] = child
        if not isinstance(child, dict):
            raise RecipeError(f"{label}: {'.'.join(parts[:index + 1])} is a value, not a table")
        target = child
        index += 1
    target[parts[-1]] = value


def _emitter_table(table: dict, parts: list[str], index: int, label: str) -> tuple[dict, int]:
    """The emitter table a --set key names, and the index of the key part after the emitter."""
    emitters = table.get("emitter")
    if not isinstance(emitters, list) or not emitters:
        raise RecipeError(f"{label}: the recipe has no [[emitter]]")
    match = EMITTER_BY_INDEX.match(parts[index])
    if match:
        position = int(match.group(1))
        if position >= len(emitters):
            raise RecipeError(f"{label}: emitter[{position}] does not exist; the recipe has "
                              f"{len(emitters)}")
        return _emitter_at(emitters, position, label), index + 1
    if len(parts) < index + 3:
        raise RecipeError(f"{label}: name the emitter, as emitter.<name>.<key> or emitter[0].<key>")
    name = parts[index + 1]
    names = [e.get("name") if isinstance(e, dict) else None for e in emitters]
    if name not in names:
        raise RecipeError(f"{label}: no emitter is named {name!r}; emitters are "
                          f"{', '.join(str(n) for n in names)}")
    return _emitter_at(emitters, names.index(name), label), index + 2


def _emitter_at(emitters: list, position: int, label: str) -> dict:
    emitter = emitters[position]
    if not isinstance(emitter, dict):
        raise RecipeError(f"{label}: emitter[{position}] is not a table")
    return emitter
