import os
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

TASK_ID_RE = re.compile(r"^[0-9a-f]{32}$")
ACTIVE_STATUSES = ("queued", "downloading", "processing")
PUBLIC_FIELDS = ("status", "percent", "speed", "eta", "filename", "error")


class QueueFullError(Exception):
    pass


class JobManager:
    """Runs downloads in background threads. Each job writes into its own
    downloads/<task_id>/ folder, which is deleted once the file is served or expires."""

    def __init__(self, root_dir, max_workers=2, max_pending=10, ttl_seconds=900):
        self.root_dir = root_dir
        self.max_pending = max_pending
        self.ttl = ttl_seconds
        self._jobs = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="download")
        os.makedirs(root_dir, exist_ok=True)

    def submit(self, kind, work):
        """work(out_dir, progress_hook) must download into out_dir and return the file path."""
        with self._lock:
            active = sum(1 for j in self._jobs.values() if j["status"] in ACTIVE_STATUSES)
            if active >= self.max_pending:
                raise QueueFullError("The server is busy with other downloads. Please try again in a minute.")
            task_id = uuid.uuid4().hex
            out_dir = os.path.join(self.root_dir, task_id)
            os.makedirs(out_dir)
            self._jobs[task_id] = {
                "kind": kind,
                "status": "queued",
                "percent": 0,
                "speed": "",
                "eta": "",
                "filename": None,
                "error": None,
                "path": None,
                "dir": out_dir,
                "created": time.time(),
            }
        self._executor.submit(self._run, task_id, out_dir, work)
        return task_id

    def _run(self, task_id, out_dir, work):
        self.update(task_id, status="downloading")
        try:
            path = work(out_dir, self._progress_hook(task_id))
            if not path or not os.path.isfile(path):
                raise RuntimeError("Download finished but the output file is missing")
            self.update(task_id, status="completed", percent=100, speed="", eta="",
                        path=path, filename=os.path.basename(path))
            print(f"🎉 [JOB {task_id[:8]}] Ready: '{os.path.basename(path)}'")
        except Exception as e:
            shutil.rmtree(out_dir, ignore_errors=True)
            self.update(task_id, status="error", error=str(e))
            print(f"❌ [JOB {task_id[:8]}] {e}")

    def _progress_hook(self, task_id):
        def hook(d):
            status = d.get('status')
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                speed = d.get('speed') or 0
                eta = d.get('eta')
                self.update(
                    task_id,
                    status="downloading",
                    percent=round(downloaded / total * 100, 1) if total > 0 else 0,
                    speed=f"{speed / (1024*1024):.1f} MB/s" if speed > 0 else "",
                    eta=f"{eta}s" if eta is not None else "",
                )
            elif status == 'finished':
                self.update(task_id, status="processing", percent=99.0, speed="", eta="")
        return hook

    def update(self, task_id, **fields):
        with self._lock:
            job = self._jobs.get(task_id)
            if job:
                job.update(fields)

    def get(self, task_id):
        with self._lock:
            job = self._jobs.get(task_id)
            return dict(job) if job else None

    def public_view(self, task_id):
        job = self.get(task_id)
        return {k: job[k] for k in PUBLIC_FIELDS} if job else None

    def release(self, task_id):
        """Forget a job and delete its files (called after the file has been served)."""
        with self._lock:
            job = self._jobs.pop(task_id, None)
        if job:
            shutil.rmtree(job["dir"], ignore_errors=True)

    def cleanup(self):
        """Delete finished jobs older than the TTL, plus leftover job folders from earlier runs."""
        now = time.time()
        with self._lock:
            expired = [tid for tid, j in self._jobs.items()
                       if j["status"] not in ACTIVE_STATUSES and now - j["created"] > self.ttl]
            known = set(self._jobs)
        for task_id in expired:
            self.release(task_id)

        # Only touch folders named like a task id, never other files in downloads/
        for name in os.listdir(self.root_dir):
            path = os.path.join(self.root_dir, name)
            if (TASK_ID_RE.match(name) and name not in known and os.path.isdir(path)
                    and now - os.path.getmtime(path) > self.ttl):
                shutil.rmtree(path, ignore_errors=True)

    def start_janitor(self, interval_seconds=60):
        def loop():
            while True:
                time.sleep(interval_seconds)
                try:
                    self.cleanup()
                except Exception as e:
                    print(f"⚠️ [JANITOR] {e}")
        threading.Thread(target=loop, name="downloads-janitor", daemon=True).start()
