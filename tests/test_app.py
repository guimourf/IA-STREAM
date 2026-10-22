import json

import pytest
from fastapi.testclient import TestClient

import app as app_module


class FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeClient:
    last_json = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        FakeClient.last_json = json
        return FakeResponse(
            200,
            {"value": "ek_test", "expires_at": 123, "session": {"id": "sess_test"}},
        )


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    monkeypatch.setattr(app_module, "CONFIG_PATH", tmp_path / "config.json")
    FakeClient.last_json = None


def test_root_is_an_api_index_without_the_prompt():
    client = TestClient(app_module.app)
    page = client.get("/")
    contract = client.get("/v1/assistant")

    assert page.status_code == 200
    assert page.json()["sessions"] == "/v1/realtime/sessions"
    assert "<html" not in page.text.lower()
    assert contract.status_code == 200
    body = contract.json()
    assert body["context_fields"][0]["key"] == "nome"
    assert body["guard_enabled"] is False
    blob = json.dumps(body, ensure_ascii=False)
    assert "scope" not in body
    assert "Substitua este bloco" not in blob
    assert client.get("/static/js/voice.js").status_code == 404


def test_session_validates_context_before_calling_openai(monkeypatch):
    monkeypatch.setattr(app_module.httpx, "AsyncClient", FakeClient)
    client = TestClient(app_module.app)

    missing = client.post("/v1/realtime/sessions", json={"context": {}})
    assert missing.status_code == 400
    assert missing.json()["detail"]["errors"][0]["field"] == "nome"
    assert FakeClient.last_json is None

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    created = client.post("/v1/realtime/sessions", json={"context": {"nome": "Ana"}})
    assert created.status_code == 200
    payload = created.json()
    assert payload["client_secret"] == "ek_test"
    assert payload["guard_enabled"] is False
    assert payload["webrtc"]["url"].endswith("/realtime/calls")
    assert "nome = Ana" in FakeClient.last_json["session"]["instructions"]
    assert FakeClient.last_json["session"]["max_output_tokens"] == 300


def test_guard_route_is_inert_while_disabled():
    client = TestClient(app_module.app)
    response = client.post("/v1/guard", json={"text": "quem ganhou o jogo?"})
    assert response.status_code == 200
    assert response.json()["allowed"] is True


def test_missing_key_is_a_controlled_error():
    client = TestClient(app_module.app)
    response = client.post("/v1/realtime/sessions", json={"context": {"nome": "Ana"}})
    assert response.status_code == 503
    assert "sk-" not in response.text


def test_service_token_protects_v1(monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "segredo")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(app_module.httpx, "AsyncClient", FakeClient)
    client = TestClient(app_module.app)

    assert client.get("/health").status_code == 200
    denied = client.post("/v1/realtime/sessions", json={"context": {"nome": "Ana"}})
    assert denied.status_code == 401
    assert FakeClient.last_json is None

    allowed = client.post(
        "/v1/realtime/sessions",
        json={"context": {"nome": "Ana"}},
        headers={"Authorization": "Bearer segredo"},
    )
    assert allowed.status_code == 200
