from __future__ import annotations

from fram_core.pipeline import _heading_sections
from scripts.ingest_project_docs import markdown_to_text


def test_markdown_to_text_strips_leading_bom_before_heading_conversion() -> None:
    rendered = markdown_to_text(
        "\ufeff# F-RAM Roadmap\n\n## Next Steps\n\n"
        "### 1. Calibration & Confidence Tuning (short term)\n"
    )

    assert rendered.startswith("[h1] F-RAM Roadmap\n")
    assert [slug for _, slug in _heading_sections(rendered)] == [
        "f_ram_roadmap",
        "f_ram_roadmap_next_steps",
        "f_ram_roadmap_next_steps_1_calibration_confidence_tuning_short_term",
    ]
