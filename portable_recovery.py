"""Offline recovery of the exact bundled Starlette files before importing FastAPI."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from datetime import datetime
import zipfile

REQUIRED_MODULES = (
    "starlette", "fastapi", "uvicorn", "anyio", "h11", "click", "pydantic",
    "pydantic_core", "python_multipart", "typing_extensions", "numpy",
    "scipy", "soundfile", "librosa", "onnxruntime", "basic_pitch", "music21",
)


def digest(file: Path) -> str:
    hasher = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def safe_relative(value: str) -> Path:
    rel = PurePosixPath(value)
    if rel.is_absolute() or ".." in rel.parts or "\\" in value or ":" in value:
        raise RuntimeError("복구 자료에 안전하지 않은 파일 경로가 있습니다.")
    if not (value.startswith("runtime/Lib/site-packages/starlette/")
            or value.startswith("runtime/Lib/site-packages/starlette-1.9.0.dist-info/")):
        raise RuntimeError("복구 범위를 벗어난 파일입니다.")
    return Path(*rel.parts)


def ensure_starlette(base: Path, data: Path) -> list[str]:
    archive = base / "support" / "starlette-recovery.zip"
    manifest_path = base / "support" / "starlette-recovery-manifest.json"
    if not archive.is_file() or not manifest_path.is_file():
        raise RuntimeError("필수 복구 자료(support 폴더)가 없습니다. ZIP 전체를 다시 압축 해제하세요.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = []
    for item in manifest["files"]:
        target = base / safe_relative(item["path"])
        if not target.is_file() or target.stat().st_size != item["size"] or digest(target) != item["sha256"]:
            missing.append(item)
    if not missing:
        return []
    if digest(archive) != manifest["archive_sha256"]:
        raise RuntimeError("복구 ZIP의 SHA-256이 일치하지 않습니다. 원본 배포 ZIP을 다시 압축 해제하세요.")
    backup = data / "repair-backup" / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + str(os.getpid()))
    restored = []
    with zipfile.ZipFile(archive) as bundle:
        for item in missing:
            relative = safe_relative(item["path"])
            payload = bundle.read(item["path"])
            if len(payload) != item["size"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                raise RuntimeError("복구 파일이 손상되었습니다: " + item["path"])
            target = base / relative
            if target.exists():
                copy = backup / relative
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, copy)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".repair-" + str(os.getpid()))
            try:
                temporary.write_bytes(payload)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            restored.append(item["path"])
    importlib.invalidate_caches()
    return restored


def check_required_modules() -> None:
    missing = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        raise ModuleNotFoundError("필수 라이브러리가 누락되었습니다: " + ", ".join(missing)
                                  + ". ZIP 전체를 새 폴더에 압축 해제하세요. 보안 프로그램의 격리 기록도 확인할 수 있지만, 보안 기능을 끄지는 마세요.")
