"""The right panel (V13): Save and Revert, Compare and Split with the keys A and B differ in, and every
recipe key grouped by table. Defaults are dimmed, keys the recipe sets are plain, keys changed in the viewer
are highlighted with a Reset. A field's edit applies when it is let go (or on Enter), checked by `plume
check`'s rules first; a rejected edit shows the check's message beside the field.
"""

from imgui_bundle import imgui

from plume.recipe.schema import LOOK_STAGE, PREVIEW_STAGE, RENDER_STAGE, SHEET_STAGE, SIMULATION_STAGE
from plume.view.recipe_keys import CHOICE, FLOAT, READ_ONLY, TEXT, VECTOR, WHOLE, KeyValue, flat_values, values_by_path
from plume.view.session import Session

LABEL_PX = 180  # the field column starts here
EDITED_COLOR = (1.0, 0.8, 0.3, 1.0)
FIELD_ERROR_COLOR = (1.0, 0.4, 0.4, 1.0)
DIFFERENCES_SHOWN = 16
STAGE_LABELS = {SIMULATION_STAGE: "re-runs", RENDER_STAGE: "redraw only", SHEET_STAGE: "redraw only",
                LOOK_STAGE: "redraw only", PREVIEW_STAGE: "under Preview"}


class EditingPanel:
    """The panel's state between window updates; the viewport reads `showing_b` and `split`."""

    def __init__(self, session: Session):
        self.session = session
        self.showing_b = False  # Compare: the viewport shows B
        self.split = False  # A and B side by side
        self.pending: dict[str, object] = {}  # a field's value while it is being dragged or typed
        self.field_errors: dict[str, str] = {}  # the check's message beside a rejected field

    def draw(self) -> None:
        """Save, Revert, Compare, then every key grouped by table."""
        session = self.session
        count = len(session.edits)
        imgui.begin_disabled(count == 0)
        if imgui.button("Save (Ctrl+S)"):
            session.save()
        imgui.same_line()
        if imgui.button("Revert"):
            session.revert()
            self.field_errors.clear()
        imgui.end_disabled()
        imgui.same_line()
        imgui.text(f"{count} unsaved edit{'s' if count != 1 else ''}" if count else "no unsaved edits")
        if session.notice:
            imgui.text_wrapped(session.notice)
        imgui.separator()
        self._compare_section()
        imgui.separator()
        groups: dict[str, list[KeyValue]] = {}
        for entry in flat_values(session.base_recipe):
            groups.setdefault(entry.info.group, []).append(entry)
        for group, entries in groups.items():
            stage = entries[0].info.stage
            title = f"{group or 'seed'}  ({STAGE_LABELS[stage]})"
            edited = sum(entry.info.path in session.edits for entry in entries)
            if edited:
                title += f"  *{edited}"
            if imgui.collapsing_header(f"{title}###group:{group}", imgui.TreeNodeFlags_.default_open):
                for entry in entries:
                    self._field(entry)

    def _compare_section(self) -> None:
        session = self.session
        compare = session.compare
        imgui.begin_disabled(compare is None)
        if imgui.button("Showing B (C)" if self.showing_b else "Compare (C)"):
            self.showing_b = not self.showing_b
        imgui.same_line()
        _, self.split = imgui.checkbox("Split", self.split)
        imgui.end_disabled()
        if compare is None:
            imgui.text_disabled("Compare: B is the run before the next change")
            return
        differences = session.compare_differences()
        if not differences:
            imgui.text("A and B have the same recipe")
            return
        imgui.text(f"A and B differ in {len(differences)} key{'s' if len(differences) != 1 else ''}:")
        before, after = values_by_path(compare.recipe), values_by_path(session.recipe)
        for path in differences[:DIFFERENCES_SHOWN]:
            imgui.bullet_text(f"{path}: {_shown_value(before.get(path))} -> {_shown_value(after.get(path))}")
        if len(differences) > DIFFERENCES_SHOWN:
            imgui.text_disabled(f"and {len(differences) - DIFFERENCES_SHOWN} more")

    def _field(self, entry: KeyValue) -> None:
        """One key: its name (dimmed when defaulted, highlighted when edited), the widget, Reset, its unit
        and the check's message when an edit was rejected."""
        session = self.session
        info, value = entry.info, entry.value
        path = info.path
        edited = path in session.edits
        imgui.push_id(path)
        imgui.align_text_to_frame_padding()
        name = path[len(info.group) + 1:] if info.group else path
        if edited:
            imgui.text_colored(imgui.ImVec4(*EDITED_COLOR), name)
        elif session.is_set_by_recipe(path):
            imgui.text(name)
        else:
            imgui.text_disabled(name)
        if imgui.is_item_hovered() and info.doc:
            imgui.set_tooltip(f"{info.doc}{f' ({info.unit})' if info.unit else ''}")
        imgui.same_line(LABEL_PX)
        imgui.set_next_item_width(-(70 if edited else 30))
        self._widget(info, value)
        if info.unit:
            imgui.same_line()
            imgui.text_disabled(info.unit)
        if edited:
            imgui.same_line()
            if imgui.small_button("Reset"):
                self._report(path, session.reset(path))
        if path in self.field_errors:
            imgui.push_text_wrap_pos(0.0)
            imgui.text_colored(imgui.ImVec4(*FIELD_ERROR_COLOR), self.field_errors[path])
            imgui.pop_text_wrap_pos()
        imgui.pop_id()

    def _widget(self, info, value) -> None:
        path = info.path
        shown = self.pending.get(path, value)
        if info.kind == READ_ONLY:
            imgui.text_disabled(_shown_value(value))
            return
        if info.kind == CHOICE:
            if imgui.begin_combo("##value", str(value)):
                for choice in info.choices:
                    if imgui.selectable(choice, choice == value)[0] and choice != value:
                        self.commit(path, choice)
                imgui.end_combo()
            return
        if info.kind == TEXT:
            changed, text = imgui.input_text("##value", str(shown), imgui.InputTextFlags_.enter_returns_true)
            if changed:
                self.commit(path, text)
            return
        if info.kind == FLOAT:
            changed, new = imgui.drag_float("##value", float(shown), _drag_step(value), 0.0, 0.0, "%.6g")
        elif info.kind == WHOLE:
            changed, new = imgui.drag_int("##value", int(shown), max(_drag_step(value), 0.05))
        elif info.kind == VECTOR:
            step = _drag_step(max((abs(component) for component in value), default=0.0))
            changed, new = imgui.drag_float3("##value", [float(component) for component in shown], step, 0.0, 0.0,
                                             "%.5g")
            new = tuple(new)
        else:
            return
        if changed:
            self.pending[path] = new
        if imgui.is_item_deactivated_after_edit():
            self.commit(path, self.pending.pop(path, new))
        elif not imgui.is_item_active():
            self.pending.pop(path, None)

    def commit(self, path: str, value) -> None:
        self._report(path, self.session.edit(path, value))

    def _report(self, path: str, error: str | None) -> None:
        if error:
            self.field_errors[path] = error
        else:
            self.field_errors.pop(path, None)


def _drag_step(value: float) -> float:
    """A drag field's step per pixel: about 1 percent of the value's size, or a small fixed step at 0 (the
    schema has no ranges)."""
    return abs(value) * 0.01 if value else 0.001


def _shown_value(value) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, tuple):
        return "[" + ", ".join(_shown_value(item) for item in value) + "]"
    return repr(value) if isinstance(value, str) else str(value)
