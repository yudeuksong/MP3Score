"""Additional Windows portability and local-service security checks."""
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from app import server, transcribe


def test_pid_probe_does_not_terminate_child():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        assert server._pid_alive(child.pid)
        assert child.poll() is None
    finally:
        child.terminate()
        child.wait(timeout=10)
    assert not server._pid_alive(child.pid)


def test_cross_origin_upload_is_rejected():
    with TestClient(server.app) as client:
        response = client.post("/api/transcribe", headers={"Origin": "https://example.com"},
                               files={"file": ("test.wav", b"not audio")})
    assert response.status_code == 403


def test_cross_site_delete_is_rejected():
    with TestClient(server.app) as client:
        response = client.delete("/api/jobs/missing", headers={"sec-fetch-site": "cross-site"})
    assert response.status_code == 403


def test_untrusted_host_is_rejected():
    with TestClient(server.app) as client:
        response = client.get("/api/info", headers={"host": "attacker.invalid"})
    assert response.status_code == 400


def test_basic_pitch_model_is_bundled():
    info = transcribe.basic_pitch_info()
    assert info.available, info.detail
    assert transcribe._onnx_model_path().stat().st_size > 100000


def test_korean_spaced_path_conversion(media, tmp_path):
    from app.pipeline import PipelineOptions, run
    from app.postprocess import ScoreParams
    import shutil
    folder = tmp_path / "한글 경로" / "시험 음원"
    folder.mkdir(parents=True)
    source = folder / "피아노 화음.mp3"
    shutil.copyfile(media["chords_mp3"], source)
    result = run(source, folder / "악보 결과", PipelineOptions(
        engine="basicpitch", make_pdf=False, score=ScoreParams(bpm=120)))
    assert result.engine == "basicpitch"
    assert result.notes_kept > 0
    assert (folder / "악보 결과" / result.files["musicxml"]).is_file()


def test_shutdown_waits_for_active_work():
    import threading
    import time
    jdir = server.ROOT / "shutdown_wait_check"
    jdir.mkdir(parents=True, exist_ok=True)
    job = server.Job("shutdown_wait_check", jdir, "synthetic.wav", status="running")
    server.JOBS[job.id] = job
    observation = {}
    def finish():
        time.sleep(0.3)
        observation["work_dir_preserved"] = jdir.exists()
        job.status = "done"
    worker = threading.Thread(target=finish)
    with TestClient(server.app):
        worker.start()
    worker.join(timeout=5)
    assert observation.get("work_dir_preserved") is True
    assert not jdir.exists()
