"""Builds schema dataclasses from parsed TOML tables, checking every key's name and type."""

import dataclasses
import difflib
import math
import typing
from typing import Any

from plume.recipe.errors import RecipeError
from plume.recipe.schema import field_info

# Top-level tables a recipe may carry that are information only (the settings log's derived values).
IGNORED_TOP_LEVEL = ("resolved",)


def build(cls: type, table: dict[str, Any], where: str = "") -> Any:
    """Builds `cls` from `table`, filling defaults; raises RecipeError naming the offending key."""
    fields = {f.name: f for f in dataclasses.fields(cls)}
    hints = typing.get_type_hints(cls)
    ignored = IGNORED_TOP_LEVEL if where == "" else ()
    for key in table:
        if key not in fields and key not in ignored:
            raise RecipeError(_unknown_key_message(_join(where, key), key, list(fields)))
    values = {}
    for name, field in fields.items():
        key_path = _join(where, name)
        if field_info(field)["section"]:
            values[name] = build(hints[name], _table_or_error(table.get(name, {}), key_path), key_path)
        elif name in table:
            values[name] = _convert(table[name], hints[name], key_path, field)
        elif field.default is dataclasses.MISSING:
            raise RecipeError(f"{key_path} is required")
        else:
            values[name] = field.default
    return cls(**values)


def _convert(value: Any, annotation: Any, key_path: str, field: dataclasses.Field) -> Any:
    origin = typing.get_origin(annotation)
    if annotation is float:
        return _number(value, key_path)
    if annotation is int:
        return _whole_number(value, key_path)
    if annotation is str:
        return _text(value, key_path, field_info(field)["choices"])
    if origin is tuple:
        return _sequence(value, typing.get_args(annotation), key_path, field)
    raise TypeError(f"schema type {annotation!r} of {key_path} has no converter")


def _sequence(value: Any, args: tuple, key_path: str, field: dataclasses.Field) -> tuple:
    if not isinstance(value, list):
        hint = f" (write [[{key_path}]] for each one)" if isinstance(value, dict) else ""
        raise RecipeError(f"{key_path} must be a list, got {_describe(value)}{hint}")
    if len(args) == 2 and args[1] is Ellipsis:
        item_type = args[0]
        if dataclasses.is_dataclass(item_type):
            return tuple(build(item_type, _table_or_error(item, f"{key_path}[{i}]"), f"{key_path}[{i}]")
                         for i, item in enumerate(value))
        return tuple(_convert(item, item_type, f"{key_path}[{i}]", field) for i, item in enumerate(value))
    if len(value) != len(args):
        raise RecipeError(f"{key_path} must have {len(args)} values, got {len(value)}")
    return tuple(_convert(item, item_type, f"{key_path}[{i}]", field)
                 for i, (item, item_type) in enumerate(zip(value, args)))


def _number(value: Any, key_path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecipeError(f"{key_path} must be a number, got {_describe(value)}")
    try:
        number = float(value)
    except OverflowError:
        number = math.inf
    # nan and inf slip past every range rule (comparisons with nan are False) and fail deep in a run.
    if not math.isfinite(number):
        raise RecipeError(f"{key_path} must be a finite number, got {number}")
    return number


def _whole_number(value: Any, key_path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RecipeError(f"{key_path} must be a whole number, got {_describe(value)}")
    return value


def _text(value: Any, key_path: str, choices: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        raise RecipeError(f"{key_path} must be text, got {_describe(value)}")
    if choices and value not in choices:
        raise RecipeError(f"{key_path} must be one of {', '.join(choices)}; got {value!r}")
    return value


def _table_or_error(value: Any, key_path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RecipeError(f"{key_path} must be a table, got {_describe(value)}")
    return value


def _unknown_key_message(key_path: str, key: str, valid: list[str]) -> str:
    close = difflib.get_close_matches(key, valid, n=1, cutoff=0.6)
    hint = f"; did you mean {close[0]}?" if close else f"; valid keys are {', '.join(valid)}"
    return f"unknown key {key_path}{hint}"


def _describe(value: Any) -> str:
    return f"{type(value).__name__} {value!r}"


def _join(where: str, name: str) -> str:
    return f"{where}.{name}" if where else name
