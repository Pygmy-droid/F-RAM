from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from fram_core.visual_evidence import (
    classify_visual_origin,
    parse_extensions,
    scan_visual_evidence,
    write_visual_manifest,
)


def _minimal_png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)


def _minimal_jpeg(width: int, height: int) -> bytes:
    component_data = b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    sof = b"\xff\xc0" + struct.pack(">H", 8 + len(component_data))
    return b"\xff\xd8" + sof + b"\x08" + struct.pack(">HH", height, width) + component_data + b"\xff\xd9"


class VisualEvidenceTests(unittest.TestCase):
    def test_scan_preserves_duplicate_paths_and_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Images").mkdir()
            payload = _minimal_png(32, 16)
            (root / "Images" / "first.png").write_bytes(payload)
            (root / "copy.png").write_bytes(payload)
            (root / "diagram.svg").write_text(
                '<svg viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg"></svg>',
                encoding="utf-8",
            )

            report = scan_visual_evidence(root)

            self.assertTrue(report.complete)
            self.assertEqual(len(report.records), 3)
            png_records = [record for record in report.records if record.extension == ".png"]
            self.assertEqual({(record.width, record.height) for record in png_records}, {(32, 16)})
            self.assertEqual({record.duplicate_count for record in png_records}, {2})
            self.assertEqual(len(report.duplicate_groups()), 1)
            self.assertEqual(report.summary()["unique_content"], 2)
            self.assertEqual(report.summary()["unique_visual_content"], 2)
            self.assertEqual(report.summary()["exact_visual_duplicate_files"], 1)
            self.assertEqual(report.summary()["actual_visuals"], 3)

    def test_appledouble_sidecar_is_retained_but_not_counted_as_a_picture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "._painting.png").write_bytes(b"AppleDouble metadata")

            report = scan_visual_evidence(root)

            self.assertTrue(report.complete)
            self.assertEqual(len(report.records), 1)
            self.assertEqual(report.records[0].content_class, "mac_metadata_sidecar")
            self.assertEqual(report.records[0].origin_class, "mac_metadata")
            self.assertEqual(report.summary()["actual_visuals"], 0)
            self.assertEqual(report.summary()["metadata_sidecars"], 1)

    def test_content_signature_overrides_a_mislabeled_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "painting.png").write_bytes(_minimal_jpeg(80, 45))

            report = scan_visual_evidence(root)

            record = report.records[0]
            self.assertEqual(record.detected_format, "jpeg")
            self.assertFalse(record.extension_matches_content)
            self.assertEqual((record.width, record.height), (80, 45))
            self.assertEqual(record.content_class, "visual")
            self.assertEqual(report.summary()["extension_mismatches"], 1)

    def test_windows_icon_is_part_of_the_visual_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # ICO header: reserved, type=icon, count=1, 32x16 first image.
            (root / "app.ico").write_bytes(b"\x00\x00\x01\x00\x01\x00\x20\x10")

            report = scan_visual_evidence(root)

            record = report.records[0]
            self.assertEqual(record.detected_format, "ico")
            self.assertEqual((record.width, record.height), (32, 16))
            self.assertEqual(record.content_class, "visual")

    def test_manifest_writes_auditable_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            output = Path(temporary) / "ledger"
            root.mkdir()
            (root / "image.png").write_bytes(_minimal_png(7, 9))

            report = scan_visual_evidence(root)
            paths = write_visual_manifest(report, output)

            self.assertTrue(paths.manifest.exists())
            summary = json.loads(paths.summary.read_text(encoding="utf-8"))
            records = [json.loads(line) for line in paths.manifest.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(summary["completeness_status"], "complete")
            self.assertEqual(summary["manifest_sha256"], json.loads(paths.duplicates.read_text())["manifest_sha256"])
            self.assertEqual(records[0]["evidence_id"], f"visual:sha256:{records[0]['sha256']}")

    def test_origin_and_extension_normalization(self) -> None:
        self.assertEqual(
            classify_visual_origin(
                "2026-07-16/F-RAM/FRAM_V22_Starter/fram_v22_starter/docs/diagram.png"
            ),
            "archive_mirror",
        )
        self.assertEqual(parse_extensions(["PNG,jpg", ".SVG"]), frozenset({".png", ".jpg", ".svg"}))


if __name__ == "__main__":
    unittest.main()
