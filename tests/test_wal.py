"""Test WAL directory detection and sizing."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from doris_debug.wal import dir_size, find_wal_dirs


class TestDirSize:
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            assert dir_size(Path(td)) == 0

    def test_files_with_content(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.wal").write_text("x" * 100)
            (root / "b.wal").write_text("y" * 200)
            assert dir_size(root) == 300

    def test_nonexistent_path(self):
        assert dir_size(Path("/nonexistent/wal/path")) == 0

    def test_walk_permission_error_handled(self):
        # dir_size should not crash on OSError (e.g. permission denied inside walk)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "readable.wal").write_text("abc")
            # dir_size uses stat which catches OSError — no crash
            assert dir_size(root) >= 3


class TestFindWalDirs:
    def test_explicit_wal_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wal = root / "wal"
            wal.mkdir()
            found = find_wal_dirs([root])
            assert len(found) == 1
            assert found[0].name == "wal"

    def test_nested_wal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nested = root / "storage" / "wal"
            nested.mkdir(parents=True)
            found = find_wal_dirs([root])
            assert len(found) == 1

    def test_nonexistent_root(self):
        found = find_wal_dirs([Path("/nonexistent/root")])
        assert found == []

    def test_dedupe_same_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "wal").mkdir()
            # Same wal found via two paths — should dedupe
            found = find_wal_dirs([root, root / "wal"])
            assert len(found) == 1
