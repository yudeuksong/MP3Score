"""Regression checks for the user's missing-Starlette startup failure."""
from pathlib import Path
import shutil

import pytest

from portable_recovery import ensure_starlette, safe_relative

SOURCE = Path(__file__).resolve().parents[1]


def recovery_copy(tmp_path):
    base = tmp_path / "한글 복구 시험"
    shutil.copytree(SOURCE / "support", base / "support")
    return base, base / "portable-data"


def test_restore_missing_starlette_before_fastapi_import(tmp_path):
    base, data = recovery_copy(tmp_path)
    restored = ensure_starlette(base, data)
    assert len(restored) == 43
    assert (base / "runtime/Lib/site-packages/starlette/__init__.py").is_file()
    assert (base / "runtime/Lib/site-packages/starlette/middleware/base.py").is_file()
    assert (base / "runtime/Lib/site-packages/starlette-1.9.0.dist-info/METADATA").is_file()


def test_clean_install_needs_no_rewrite(tmp_path):
    base, data = recovery_copy(tmp_path)
    ensure_starlette(base, data)
    file = base / "runtime/Lib/site-packages/starlette/__init__.py"
    stamp = file.stat().st_mtime_ns
    assert ensure_starlette(base, data) == []
    assert file.stat().st_mtime_ns == stamp


def test_corrupted_file_is_backed_up_before_restore(tmp_path):
    base, data = recovery_copy(tmp_path)
    ensure_starlette(base, data)
    file = base / "runtime/Lib/site-packages/starlette/__init__.py"
    original = file.read_bytes()
    file.write_bytes(b"broken test file")
    restored = ensure_starlette(base, data)
    assert len(restored) == 1
    assert file.read_bytes() == original
    copies = list((data / "repair-backup").rglob("__init__.py"))
    assert len(copies) == 1 and copies[0].read_bytes() == b"broken test file"


def test_bad_recovery_archive_is_rejected(tmp_path):
    base, data = recovery_copy(tmp_path)
    file = base / "support/starlette-recovery.zip"
    file.write_bytes(file.read_bytes() + b"corruption")
    with pytest.raises(RuntimeError, match="SHA-256"):
        ensure_starlette(base, data)
    assert not (base / "runtime").exists()


@pytest.mark.parametrize("path", ["../elsewhere.py", "runtime/Lib/site-packages/not-starlette/elsewhere.py"])
def test_recovery_paths_are_restricted(path):
    with pytest.raises(RuntimeError):
        safe_relative(path)
