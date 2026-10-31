import json

import pytest

from fram_eval.datasets import load_jsonl, synthetic_layout_cases, write_jsonl


def test_jsonl_dataset_round_trip_preserves_metadata(tmp_path):
    source = tmp_path / "eval.jsonl"
    source.write_text(
        json.dumps(
            {
                "id": "case-1",
                "query": "Where is the evidence?",
                "expected_ids": ["doc:1"],
                "answer": "In doc one",
                "custom_field": 7,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cases = load_jsonl(source)
    assert len(cases) == 1
    assert cases[0].case_id == "case-1"
    assert cases[0].relevant_ids == ("doc:1",)
    assert cases[0].metadata["custom_field"] == 7

    destination = tmp_path / "round-trip" / "eval.jsonl"
    assert write_jsonl(cases, destination) == destination
    assert load_jsonl(destination) == cases


def test_jsonl_dataset_reports_line_errors(tmp_path):
    source = tmp_path / "broken.jsonl"
    source.write_text('{"query": "ok"}\n{"query": }\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"broken\.jsonl:2: invalid JSON"):
        load_jsonl(source)


def test_synthetic_layout_cases_cover_required_modalities():
    cases = synthetic_layout_cases()
    assert {case.metadata["modality"] for case in cases} == {"table", "code", "pdf"}
    assert all(case.relevant_ids for case in cases)
    assert all(case.expected_citations for case in cases)
