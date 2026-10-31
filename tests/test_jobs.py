import os
import time

import pytest

from core.jobs import JobManager, QueueFullError


def wait_for(jobs, task_id, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs.get(task_id)
        if job["status"] in ("completed", "error"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def write_file(out_dir, hook):
    hook({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100, "speed": 1048576, "eta": 3})
    path = os.path.join(out_dir, "song.mp3")
    with open(path, "w") as f:
        f.write("data")
    return path


def test_successful_job_and_release(tmp_path):
    jobs = JobManager(str(tmp_path))
    task_id = jobs.submit("audio", write_file)
    job = wait_for(jobs, task_id)

    assert len(task_id) == 32
    assert job["status"] == "completed" and job["filename"] == "song.mp3"
    assert set(jobs.public_view(task_id)) == {"status", "percent", "speed", "eta", "filename", "error"}

    jobs.release(task_id)
    assert jobs.get(task_id) is None
    assert not os.path.exists(job["dir"])


def test_failed_job_cleans_up(tmp_path):
    def boom(out_dir, hook):
        raise RuntimeError("Video unavailable")

    jobs = JobManager(str(tmp_path))
    task_id = jobs.submit("video", boom)
    job = wait_for(jobs, task_id)

    assert job["status"] == "error" and job["error"] == "Video unavailable"
    assert not os.path.exists(job["dir"])


def test_queue_limit(tmp_path):
    jobs = JobManager(str(tmp_path), max_workers=1, max_pending=1)
    jobs.submit("video", lambda out_dir, hook: time.sleep(0.3))
    with pytest.raises(QueueFullError):
        jobs.submit("video", write_file)


def test_cleanup_expires_finished_jobs_and_orphans_only(tmp_path):
    jobs = JobManager(str(tmp_path), ttl_seconds=0)
    task_id = jobs.submit("audio", write_file)
    wait_for(jobs, task_id)

    orphan = tmp_path / ("a" * 32)
    orphan.mkdir()
    users_file = tmp_path / "my old download.mp4"
    users_file.write_text("keep me")
    time.sleep(0.01)

    jobs.cleanup()

    assert jobs.get(task_id) is None
    assert not orphan.exists()
    assert users_file.exists()
