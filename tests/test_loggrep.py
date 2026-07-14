"""Test loggrep: regex packs, fragment correlation, file discovery."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from doris_debug.loggrep import (
    extract_fragment_ids,
    grep_files,
    SIGNATURES,
    _find_log_files,
)


class TestExtractFragmentIds:
    def test_standard_format(self):
        lines = [
            "be/log/be.WARNING:42:fragment_instance_id=abc123-def456-7890: timeout",
        ]
        ids = extract_fragment_ids(lines)
        assert "abc123-def456-7890" in ids

    def test_instance_id_format(self):
        lines = [
            "be/log/be.WARNING:42:InstanceId=xyz789-abc-0001: failed to scan",
        ]
        ids = extract_fragment_ids(lines)
        assert "xyz789-abc-0001" in ids

    def test_no_fragment_ids(self):
        lines = [
            "be/log/be.WARNING:1:no fragment here",
            "be/log/be.WARNING:2:just a warning",
        ]
        ids = extract_fragment_ids(lines)
        assert len(ids) == 0

    def test_multiple_ids(self):
        lines = [
            "fragment_instance_id=aaa-111: error",
            "fragment_instance_id=bbb-222: retry",
            "fragment_instance_id=aaa-111: another error",
        ]
        ids = extract_fragment_ids(lines)
        assert len(ids) == 2
        assert "aaa-111" in ids
        assert "bbb-222" in ids


class TestGrepFiles:
    def test_simple_grep(self):
        import re
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "be.WARNING").write_text(
                "I20260715 everything fine\nW20260715 failed to send brpc when exchange\n"
            )
            hits = grep_files([root / "be.WARNING"], ["failed to send brpc when exchange"])
            assert len(hits) == 1
            assert "be.WARNING" in hits[0]
            assert "failed to send brpc" in hits[0]

    def test_case_insensitive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "be.WARNING").write_text(
                "W20260715 FAILED TO SEND BRPC WHEN EXCHANGE\n"
            )
            hits = grep_files([root / "be.WARNING"], ["failed to send brpc when exchange"])
            assert len(hits) == 1

    def test_max_hits(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "log").write_text("\n".join(
                f"line {i}: error" for i in range(100)
            ))
            hits = grep_files([root / "log"], ["error"], max_hits=10)
            assert len(hits) == 10

    def test_skip_non_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "subdir").mkdir()
            hits = grep_files([root / "subdir"], ["anything"])
            assert len(hits) == 0  # dir silently skipped


class TestSignatures:
    def test_known_packs_exist(self):
        assert "exchange" in SIGNATURES
        assert "versions" in SIGNATURES
        assert "group_commit" in SIGNATURES
        assert "planner" in SIGNATURES
        assert "memory" in SIGNATURES

    def test_each_pack_has_patterns(self):
        for pack_name, regexes in SIGNATURES.items():
            if pack_name != "all":
                assert len(regexes) > 0, f"Pack '{pack_name}' has no patterns"


class TestFindLogFiles:
    def test_single_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "be.WARNING").write_text("test")
            files = _find_log_files([root / "be.WARNING"])
            assert len(files) == 1

    def test_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "be.WARNING").write_text("warn")
            (root / "be.INFO").write_text("info")
            (root / "be.log").write_text("log")
            (root / "random.txt").write_text("txt")
            files = _find_log_files([root])
            names = {f.name for f in files}
            assert "be.WARNING" in names
            assert "be.INFO" in names
            assert "be.log" in names
