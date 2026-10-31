from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.ingest import ingest_demo_corpus, main as ingest_main


def _expected_persist_paths(storage_root: Path) -> tuple[Path, Path]:
    cfg = FRAMConfig()
    index_dir = storage_root / cfg.STORAGE_SUBFOLDERS.get("index", "index")
    claims_dir = storage_root / cfg.STORAGE_SUBFOLDERS.get("claims", "claims")
    return index_dir / "demo_corpus", claims_dir / "demo_corpus.jsonl"


def test_ingest_demo_corpus_persists_assets(tmp_path):
    storage_root = tmp_path / "storage"
    persist_path = ingest_demo_corpus(storage_root=storage_root)

    corpus_path, claims_path = _expected_persist_paths(storage_root)
    assert persist_path == corpus_path
    assert (corpus_path / "chunks.json").exists()
    assert (corpus_path / "vocab.json").exists()
    assert (corpus_path / "chunk_vecs.npy").exists()
    assert claims_path.exists()


def test_ingest_demo_corpus_custom_subdir(tmp_path):
    storage_root = tmp_path / "storage"
    persist_path = ingest_demo_corpus(storage_root=storage_root, persist_subdir="custom")

    cfg = FRAMConfig()
    index_dir = storage_root / cfg.STORAGE_SUBFOLDERS.get("index", "index")
    custom_path = index_dir / "custom"
    assert persist_path == custom_path
    assert (custom_path / "chunks.json").exists()


def test_ingest_cli_main_quiet(tmp_path, capsys):
    storage_root = tmp_path / "store"
    exit_code = ingest_main(["--storage-root", str(storage_root), "--quiet"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    assert out
    assert (Path(out) / "chunks.json").exists()
