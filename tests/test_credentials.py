"""Google OAuth client file: upload from Settings and auto-detect in the project folder."""
import json

from backend import gmail_client
from conftest import desktop_client_json


def test_status_when_nothing_uploaded(client, project_dir):
    assert client.get("/api/settings/credentials").json() == {"has_credentials": False, "has_token": False}


def test_upload_saves_credentials_json(client, project_dir):
    r = client.post("/api/settings/credentials", json={"content": desktop_client_json()})
    assert r.status_code == 200 and r.json()["saved"] is True
    assert json.loads((project_dir / "credentials.json").read_text())["installed"]["client_secret"] == "s3cret"
    assert client.get("/api/settings/credentials").json()["has_credentials"] is True


def test_web_client_is_rejected_with_a_helpful_message(client, project_dir):
    r = client.post("/api/settings/credentials", json={"content": json.dumps({"web": {"client_id": "x"}})})
    assert r.status_code == 400
    assert "Desktop app" in r.json()["detail"]
    assert not (project_dir / "credentials.json").exists()


def test_garbage_is_rejected(client, project_dir):
    for bad in ["not json", "[]", json.dumps({"installed": {}}), json.dumps({"hello": 1})]:
        r = client.post("/api/settings/credentials", json={"content": bad})
        assert r.status_code == 400, bad
    assert not (project_dir / "credentials.json").exists()


def test_replacing_with_a_different_client_drops_the_old_login(client, project_dir):
    client.post("/api/settings/credentials", json={"content": desktop_client_json("old")})
    (project_dir / "token.json").write_text("{}")
    r = client.post("/api/settings/credentials", json={"content": desktop_client_json("new")})
    assert r.json() == {"saved": True, "replaced": True, "token_removed": True}
    assert not (project_dir / "token.json").exists()


def test_reuploading_the_same_file_keeps_the_login(client, project_dir):
    client.post("/api/settings/credentials", json={"content": desktop_client_json()})
    (project_dir / "token.json").write_text("{}")
    r = client.post("/api/settings/credentials", json={"content": desktop_client_json()})
    assert r.json()["token_removed"] is False
    assert (project_dir / "token.json").exists()


# --- auto-detect a downloaded client_secret_*.json dropped in the project folder ---

def test_adopt_renames_a_desktop_client_file(project_dir):
    (project_dir / "client_secret_123.json").write_text(desktop_client_json())
    assert gmail_client.adopt_credentials(project_dir) == project_dir / "credentials.json"
    assert not (project_dir / "client_secret_123.json").exists()


def test_adopt_ignores_other_json(project_dir):
    (project_dir / "token.json").write_text(json.dumps({"token": "x", "refresh_token": "y"}))
    (project_dir / "notes.json").write_text("not json")
    (project_dir / "web.json").write_text(json.dumps({"web": {"client_id": "x", "client_secret": "y"}}))
    assert gmail_client.adopt_credentials(project_dir) is None


def test_adopt_leaves_existing_credentials_alone(project_dir):
    (project_dir / "credentials.json").write_text(desktop_client_json("keep"))
    (project_dir / "client_secret_new.json").write_text(desktop_client_json("other"))
    gmail_client.adopt_credentials(project_dir)
    assert "keep" in (project_dir / "credentials.json").read_text()
    assert (project_dir / "client_secret_new.json").exists()
