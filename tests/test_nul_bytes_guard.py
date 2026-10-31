from pathlib import Path

from tools.check_nul_bytes import find_nul_bytes, strip_nul_bytes


def test_nul_bytes_detection_and_fix(tmp_path: Path) -> None:
    target = tmp_path / "nul.md"
    target.write_bytes(b"hello\x00world")
    findings = find_nul_bytes([target])
    assert findings and findings[0].path == target

    removed = strip_nul_bytes(target)
    assert removed == 1
    assert find_nul_bytes([target]) == []


def test_repo_docs_and_prompts_have_no_nul_bytes() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    findings = find_nul_bytes([repo_root / "docs", repo_root / "prompts"])
    assert findings == []

