"""Turns a resolved recipe back into TOML text, the form the settings log and `plume check` print."""

import dataclasses
from typing import Any

import tomli_w

from plume.recipe.derived import Derived
from plume.recipe.schema import Recipe


def recipe_to_toml(recipe: Recipe, derived: Derived, device: str) -> str:
    """The recipe with every value explicit, plus a [resolved] table of derived values (ignored on load)."""
    table = _plain(dataclasses.asdict(recipe))
    table["resolved"] = {
        "cells": list(derived.cells),
        "size_m": list(derived.size_m),
        "fps": derived.fps,
        "dt_s": derived.dt_s,
        "warmup_steps": derived.warmup_steps,
        "device": device,
    }
    return tomli_w.dumps(table)


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value
