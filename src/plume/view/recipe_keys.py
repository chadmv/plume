"""A resolved recipe as a flat list of keys, for the editing panel and Compare.

Key paths use `--set`'s grammar (`forces.turbulence.scale_m`, `emitter.puff.radius_m`), so an edit applies
through the same code as a command-line override. Emitters are named by their `name`, which the rules keep
unique. What a key is (its type, unit, description, choices and stage) comes from the schema.
"""

import dataclasses
import typing
from dataclasses import dataclass
from typing import Any

from plume.recipe.schema import EmitterSettings, Recipe, Vec3, field_info, stage_of

FLOAT, WHOLE, CHOICE, TEXT, VECTOR, READ_ONLY = "float", "whole", "choice", "text", "vector", "read_only"


@dataclass(frozen=True)
class KeyInfo:
    path: str
    kind: str  # FLOAT, WHOLE, CHOICE, TEXT, VECTOR or READ_ONLY (ramps, colors, emitter names)
    unit: str
    doc: str
    choices: tuple[str, ...]
    stage: str
    group: str  # the panel's heading: the top-level table, `emitter.<name>`, or "" for top-level keys


@dataclass(frozen=True)
class KeyValue:
    info: KeyInfo
    value: Any


def flat_values(recipe: Recipe) -> list[KeyValue]:
    """Every leaf key of the recipe in schema order; `extends` is left out (it is not a value to tune)."""
    entries: list[KeyValue] = []
    hints = typing.get_type_hints(Recipe)
    for field in dataclasses.fields(Recipe):
        name = field.name
        if name == "extends":
            continue
        if name == "emitter":
            for emitter in recipe.emitter:
                group = f"emitter.{emitter.name}"
                _walk(EmitterSettings, emitter, group, group, entries)
        elif field_info(field)["section"]:
            _walk(hints[name], getattr(recipe, name), name, name, entries)
        else:
            entries.append(KeyValue(_info(field, hints[name], name, ""), getattr(recipe, name)))
    return entries


def values_by_path(recipe: Recipe) -> dict[str, Any]:
    return {entry.info.path: entry.value for entry in flat_values(recipe)}


def changed_paths(before: Recipe, after: Recipe) -> list[str]:
    """Key paths whose values differ between two recipes (a key only one has counts), in `after`'s order
    then `before`'s."""
    old, new = values_by_path(before), values_by_path(after)
    paths = list(new) + [path for path in old if path not in new]
    return [path for path in paths if old.get(path, _ABSENT) != new.get(path, _ABSENT)]


def changed_stages(before: Recipe, after: Recipe) -> set[str]:
    """The stages of every key that differs."""
    return {stage_of(path) for path in changed_paths(before, after)}


def table_paths(table: dict) -> set[str]:
    """The leaf key paths a parsed recipe table sets (a recipe merged with its parents): what the panel shows
    as set by the recipe rather than defaulted."""
    paths: set[str] = set()
    for key, value in table.items():
        if key in ("extends", "resolved"):
            continue
        if key == "emitter" and isinstance(value, list):
            for emitter in value:
                if isinstance(emitter, dict) and isinstance(emitter.get("name"), str):
                    _table_paths(emitter, f"emitter.{emitter['name']}", paths)
        elif isinstance(value, dict):
            _table_paths(value, key, paths)
        else:
            paths.add(key)
    return paths


def _table_paths(table: dict, prefix: str, paths: set[str]) -> None:
    for key, value in table.items():
        if isinstance(value, dict):
            _table_paths(value, f"{prefix}.{key}", paths)
        else:
            paths.add(f"{prefix}.{key}")


_ABSENT = object()


def _walk(cls: type, value: Any, prefix: str, group: str, entries: list[KeyValue]) -> None:
    hints = typing.get_type_hints(cls)
    for field in dataclasses.fields(cls):
        path = f"{prefix}.{field.name}"
        if field_info(field)["section"]:
            _walk(hints[field.name], getattr(value, field.name), path, group, entries)
        else:
            entries.append(KeyValue(_info(field, hints[field.name], path, group), getattr(value, field.name)))


def _info(field: dataclasses.Field, annotation: Any, path: str, group: str) -> KeyInfo:
    info = field_info(field)
    return KeyInfo(path=path, kind=_kind(field, annotation, info), unit=info["unit"], doc=info["doc"],
                   choices=info["choices"], stage=stage_of(path), group=group)


def _kind(field: dataclasses.Field, annotation: Any, info: dict) -> str:
    if annotation is float:
        return FLOAT
    if annotation is int:
        return WHOLE
    if annotation == Vec3:
        return VECTOR
    if annotation is str:
        if info["choices"]:
            return CHOICE
        # emitter names are the emitters' identities (edits find them by name); colors are edited in the file
        if field.name == "name" and field in dataclasses.fields(EmitterSettings) or info["unit"] == "sRGB":
            return READ_ONLY
        return TEXT
    return READ_ONLY  # ramps
