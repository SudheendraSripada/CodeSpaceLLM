import importlib
from base64 import b64decode


def build_client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "assistant-test.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("OWNER_PASSWORD", "owner-pass")
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    module = importlib.import_module("app.main")
    app = module.create_app()
    from fastapi.testclient import TestClient

    return TestClient(app)


def login(client, email="owner@example.com", password="owner-pass"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_admin_settings_are_protected(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        response = client.get("/api/settings")
        assert response.status_code == 401

        token = login(client)
        response = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["provider"] == "mock"


def test_chat_persists_history(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        token = login(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post("/api/chat", json={"message": "Hello assistant"}, headers=headers)
        assert response.status_code == 200, response.text
        conversation_id = response.json()["conversation"]["id"]

        messages = client.get(f"/api/chat/conversations/{conversation_id}/messages", headers=headers)
        assert messages.status_code == 200
        assert [item["role"] for item in messages.json()] == ["user", "assistant"]


def test_text_upload_is_used_in_chat_context(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        token = login(client)
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/api/files/upload",
            headers=headers,
            files={"file": ("notes.txt", b"Project launch plan: alpha, beta, release.", "text/plain")},
        )
        assert upload.status_code == 200, upload.text
        file_id = upload.json()["id"]

        chat = client.post(
            "/api/chat",
            json={"message": "Use the attached file.", "file_ids": [file_id]},
            headers=headers,
        )
        assert chat.status_code == 200, chat.text
        assert "Project launch plan" in chat.json()["message"]["content"]


def test_image_upload_reaches_model_context(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        token = login(client)
        headers = {"Authorization": f"Bearer {token}"}
        png_bytes = b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
        upload = client.post(
            "/api/files/upload",
            headers=headers,
            files={"file": ("pixel.png", png_bytes, "image/png")},
        )
        assert upload.status_code == 200, upload.text
        file_id = upload.json()["id"]

        chat = client.post(
            "/api/chat",
            json={"message": "Describe this image.", "file_ids": [file_id]},
            headers=headers,
        )
        assert chat.status_code == 200, chat.text
        assert "Image bytes attached for model vision" in chat.json()["message"]["content"]


def test_user_cannot_update_admin_settings(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        register = client.post("/api/auth/register", json={"email": "user@example.com", "password": "pass123"})
        assert register.status_code == 200, register.text
        token = register.json()["access_token"]
        response = client.put(
            "/api/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_name": "mock-local",
                "system_prompt": "Nope",
                "enabled_tools": ["datetime"],
            },
        )
        assert response.status_code == 403
