from __future__ import annotations

import os
import tempfile


TEST_DATA_DIR = tempfile.mkdtemp(prefix="meeting-app-tests-")
os.environ["MEETING_DATA_DIR"] = TEST_DATA_DIR
os.environ["MEETING_DATABASE_URL"] = f"sqlite:///{TEST_DATA_DIR}/test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
