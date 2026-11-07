"""Generates `docs/recipe-reference.md` from the schema, so the reference can never drift from the code.

Run `uv run python -m plume.recipe.reference` to rewrite it; a test fails while it is stale.
"""

import dataclasses
import typing
from pathlib import Path

from plume.recipe.schema import Recipe, field_info

REFERENCE_PATH = Path("docs/recipe-reference.md")
HEADER = """# Recipe reference

Generated from `src/plume/recipe/schema.py` by `uv run python -m plume.recipe.reference`; do not edit by
hand. Every key carries its unit in its name. Unknown keys are errors. `[look]` only changes the contact
sheets, never the sheet.
"""


def reference_markdown() -> str:
    """The whole reference document."""
    parts = [HEADER, _section_text("Top level", Recipe, "")]
    for field in dataclasses.fields(Recipe):
        hints = typing.get_type_hints(Recipe)
        if field_info(field)["section"]:
            parts.extend(_section_tree(field.name, hints[field.name], field_info(field)["doc"]))
        elif field.name == "emitter":
            item = typing.get_args(hints["emitter"])[0]
            parts.extend(_section_tree("emitter", item, field_info(field)["doc"], array=True))
    return "\n".join(parts)


def _section_tree(name: str, cls: type, doc: str, array: bool = False) -> list[str]:
    parts = [_section_text(f"[[{name}]]" if array else f"[{name}]", cls, doc)]
    hints = typing.get_type_hints(cls)
    for field in dataclasses.fields(cls):
        if field_info(field)["section"]:
            parts.extend(_section_tree(f"{name}.{field.name}", hints[field.name], field_info(field)["doc"]))
    return parts


def _section_text(title: str, cls: type, doc: str) -> str:
    lines = [f"## {title}", ""]
    if doc:
        lines += [doc, ""]
    lines += ["| key | unit | default | meaning |", "| --- | --- | --- | --- |"]
    for field in dataclasses.fields(cls):
        info = field_info(field)
        if info["section"] or (cls is Recipe and field.name == "emitter"):
            continue
        meaning = info["doc"]
        if info["choices"]:
            meaning += " One of: " + ", ".join(f"`{choice}`" for choice in info["choices"]) + "."
        lines.append(f"| `{field.name}` | {info['unit'] or '-'} | {_default_text(field)} | {meaning} |")
    return "\n".join(lines) + "\n"


def _default_text(field: dataclasses.Field) -> str:
    if field.default is dataclasses.MISSING:
        return "required"
    return f"`{_toml_value(field.default)}`"


def _toml_value(value) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, tuple):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return str(value)


if __name__ == "__main__":
    REFERENCE_PATH.write_text(reference_markdown(), newline="\n")
    print(f"wrote {REFERENCE_PATH}")
