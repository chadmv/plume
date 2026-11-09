"""Section 9's stage tests: every recipe table says what a change to it does in the viewer (V11)."""

import dataclasses

import pytest

from plume.recipe.reference import reference_markdown
from plume.recipe.schema import (LOOK_STAGE, PREVIEW_STAGE, RENDER_STAGE, SHEET_STAGE, SIMULATION_STAGE, STAGES,
                                 Recipe, field_info, stage_of)


def test_every_top_level_table_and_key_has_a_stage():
    for field in dataclasses.fields(Recipe):
        assert field_info(field)["stage"] in STAGES, f"{field.name} has no stage"


@pytest.mark.parametrize(("key", "stage"), [
    ("seed", SIMULATION_STAGE),
    ("domain.faces.top", SIMULATION_STAGE),
    ("emitter.puff.noise.strength", SIMULATION_STAGE),
    ("emitter[0].radius_m", SIMULATION_STAGE),
    ("forces.turbulence.scale_m", SIMULATION_STAGE),
    ("render.light_dir", RENDER_STAGE),
    ("camera.elevation_deg", SHEET_STAGE),
    ("output.frame_px", SHEET_STAGE),
    ("look.backgrounds.grass", LOOK_STAGE),
    ("preview.frames", PREVIEW_STAGE),
])
def test_a_key_takes_its_top_level_tables_stage(key, stage):
    assert stage_of(key) == stage


def test_the_reference_names_each_tables_stage():
    text = reference_markdown()
    assert "## [render]\n\nTurning the volume into sheet channels.\n\nStage: `render`" in text
    assert ("## [forces.turbulence]\n\nSeeded curl-noise swirls, in meters, so previews match.\n\n"
            "Stage: `simulation`") in text
    assert "## [look.backgrounds]\n\nContact sheet backgrounds.\n\nStage: `look`" in text
