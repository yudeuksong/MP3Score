"""Portable Windows entry point. All mutable application data stays beside the app."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import traceback

BASE = Path(__file__).resolve().parent
DATA = BASE / "portable-data"


def prepare_environment():
    for sub in ("temp", "logs", "cache/numba", "cache/matplotlib", "cache/pooch", "config", "local"):
        (DATA / sub).mkdir(parents=True, exist_ok=True)
    values = {
        "TMP": DATA / "temp", "TEMP": DATA / "temp", "TMPDIR": DATA / "temp",
        "APPDATA": DATA / "config", "LOCALAPPDATA": DATA / "local",
        "XDG_CACHE_HOME": DATA / "cache", "MPLCONFIGDIR": DATA / "cache/matplotlib",
        "NUMBA_CACHE_DIR": DATA / "cache/numba", "LIBROSA_DATA_DIR": DATA / "cache/pooch",
        "MUSIC21_USERDATA": DATA / "config", "PYTHONIOENCODING": "utf-8",
    }
    for key, value in values.items():
        os.environ[key] = str(value)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["MP3SCORE_PORTABLE"] = "1"
    os.environ["OMP_NUM_THREADS"] = str(min(4, os.cpu_count() or 1))
    os.environ["NUMBA_NUM_THREADS"] = str(min(4, os.cpu_count() or 1))
    sys.dont_write_bytecode = True
    os.chdir(BASE)
    runtime = BASE / "runtime"
    os.environ["PATH"] = str(runtime) + os.pathsep + os.environ.get("PATH", "")
    if os.name == "nt" and hasattr(os, "add_dll_directory") and runtime.is_dir():
        globals()["_dll_dir"] = os.add_dll_directory(str(runtime))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--parent-pid", type=int, default=0)
    ap.add_argument("--diagnose", action="store_true")
    args = ap.parse_args()
    prepare_environment()
    if args.diagnose:
        from portable_recovery import ensure_starlette, check_required_modules
        ensure_starlette(BASE, DATA)
        check_required_modules()
        print(json.dumps({"python": sys.version, "prefix": sys.prefix, "executable": sys.executable,
                          "path": sys.path, "base": str(BASE), "data": str(DATA)}, ensure_ascii=False, indent=2))
        return 0

    log_path = DATA / "logs" / "server.log"
    if log_path.exists() and log_path.stat().st_size > 5 * 1024 * 1024:
        log_path.replace(log_path.with_suffix(".previous.log"))
    stream = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream
    print("\n=== MP3 Score Portable startup v0.1.2 ===", flush=True)
    summary_path = DATA / "logs" / "error-summary.txt"
    summary_path.unlink(missing_ok=True)
    ready = DATA / "server.ready"
    stop_file = DATA / "stop.request"
    stop_file.unlink(missing_ok=True)
    server_module = None
    listener = None
    try:
        from portable_recovery import ensure_starlette, check_required_modules
        restored = ensure_starlette(BASE, DATA)
        if restored:
            print("오프라인 라이브러리 자동 복구: {}개 파일".format(len(restored)), flush=True)
        check_required_modules()
        from app import server as server_module
        from app.transcribe import basic_pitch_info
        import uvicorn
        info = basic_pitch_info()
        if not info.available:
            raise RuntimeError("Bundled Basic Pitch engine unavailable: " + info.detail)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", args.port))
        listener.listen(128)
        port = listener.getsockname()[1]
        url = "http://127.0.0.1:{}/".format(port)
        config = uvicorn.Config(server_module.app, host="127.0.0.1", port=port,
                                log_level="warning", access_log=False)
        service = uvicorn.Server(config)
        done = threading.Event()

        def monitor_stop():
            while not done.wait(0.3):
                if stop_file.exists() or (args.parent_pid and not server_module._pid_alive(args.parent_pid)):
                    service.should_exit = True
                    return
        threading.Thread(target=monitor_stop, daemon=True).start()
        ready.write_text(str(os.getpid()) + "\n" + url + "\n", encoding="utf-8")
        try:
            service.run(sockets=[listener])
        finally:
            done.set()
        return 0
    except Exception as exc:
        summary_path.write_text(type(exc).__name__ + ": " + str(exc), encoding="utf-8")
        traceback.print_exc()
        return 1
    finally:
        if server_module is not None:
            # Wait for an in-progress conversion before deleting its work folder.
            server_module._executor.shutdown(wait=True, cancel_futures=True)
            server_module._shutdown()
        if listener is not None:
            listener.close()
        try:
            if ready.exists() and ready.read_text(encoding="utf-8").splitlines()[0] == str(os.getpid()):
                ready.unlink(missing_ok=True)
            stop_file.unlink(missing_ok=True)
        except (OSError, IndexError):
            pass
        print("Portable server stopped.", flush=True)


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        traceback.print_exc()
        try:
            early_log = DATA / "logs"
            early_log.mkdir(parents=True, exist_ok=True)
            (early_log / "error-summary.txt").write_text(type(exc).__name__ + ": " + str(exc), encoding="utf-8")
            with (early_log / "startup-error.log").open("a", encoding="utf-8") as output:
                traceback.print_exc(file=output)
        except OSError:
            pass
        code = 1
    raise SystemExit(code)
