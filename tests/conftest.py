import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import server
    from core.jobs import JobManager

    monkeypatch.setattr(server, "jobs", JobManager(str(tmp_path), max_workers=1, max_pending=2))
    server.lookup_limit.reset()
    server.download_limit.reset()
    server.heavy_limit.reset()
    return TestClient(server.app)
