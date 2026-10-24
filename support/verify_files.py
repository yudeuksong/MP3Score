"""Optional, read-only distribution integrity diagnostic (no downloads or installs)."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    manifest = json.loads((ROOT / "DISTRIBUTION-FILES.json").read_text(encoding="utf-8"))
    issues = []
    for index, item in enumerate(manifest["files"], 1):
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or ":" in item["path"] or "\\" in item["path"]:
            raise RuntimeError("안전하지 않은 진단 경로")
        file = ROOT.joinpath(*relative.parts)
        reason = None
        try:
            if not file.is_file():
                reason = "누락"
            elif file.stat().st_size != item["size"]:
                reason = "크기 불일치"
            else:
                digest = hashlib.sha256()
                with file.open("rb") as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != item["sha256"]:
                    reason = "SHA-256 불일치"
        except OSError as exc:
            reason = "읽기 실패: " + str(exc)
        if reason:
            issues.append({"path": item["path"], "reason": reason})
        if index % 1000 == 0:
            print("검사 중: {}/{}".format(index, len(manifest["files"])), flush=True)
    logs = ROOT / "portable-data/logs"
    logs.mkdir(parents=True, exist_ok=True)
    report = logs / "integrity-report.json"
    report.write_text(json.dumps({"files_checked": len(manifest["files"]), "issues": issues}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n전체 {}개 파일 검사, 이상 {}개".format(len(manifest["files"]), len(issues)))
    for issue in issues[:30]:
        print(issue["reason"] + ": " + issue["path"])
    print("상세 결과: " + str(report))
    print("이 도구는 파일을 설치·복구·삭제하지 않습니다. 수정한 소스도 변경으로 표시될 수 있습니다.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
