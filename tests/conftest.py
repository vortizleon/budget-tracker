"""Test setup: use a throwaway database and never touch the real project folder."""
import os
import tempfile
from pathlib import Path

# Must be set before backend.database is imported (it reads DATABASE_URL at import time).
_TMP = Path(tempfile.mkdtemp(prefix="budget-tracker-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"

import pytest
from fastapi.testclient import TestClient

from backend import gmail_client
from backend.api import app
from backend.database import Base, engine


@pytest.fixture
def client():
    # A fresh, empty database for every test, so tests can't affect each other.
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # runs startup -> creates tables
        yield c


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """Point the Gmail credentials code at an empty temp folder."""
    monkeypatch.setattr(gmail_client, "BASE_DIR", tmp_path)
    return tmp_path


def desktop_client_json(secret="s3cret"):
    import json
    return json.dumps({"installed": {"client_id": "123.apps.googleusercontent.com", "client_secret": secret}})
