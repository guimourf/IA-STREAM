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
    payload = {
        "value": "ek_test",
        "expires_at": 123,
        "session": {"id": "sess_test"},
    }

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        FakeClient.last_json = json
        if url.endswith("/responses"):
            return FakeResponse(
                200,
                {
                    "id": "resp_test",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "Olá, Ana."}],
                        }
                    ],
                },
            )
        return FakeResponse(200, FakeClient.payload)


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(app_module, "CONFIG_PATH", tmp_path / "config.json")
    FakeClient.last_json = None


def test_example_page_offers_both_modes_without_the_prompt():
    client = TestClient(app_module.app)
    page = client.get("/")
    stream_js = client.get("/stream/voice.js")
    response_js = client.get("/response/chat.js")

    assert page.status_code == 200
    assert 'data-mode="stream"' in page.text
    assert 'data-mode="response"' in page.text
    assert "Substitua este bloco" not in page.text
    assert stream_js.status_code == 200
    assert "response.output_audio_transcript.delta" in stream_js.text
    assert response_js.status_code == 200
    assert "/api/response" in response_js.text


def test_stream_session_validates_context_before_calling_openai(monkeypatch):
    monkeypatch.setattr(app_module.httpx, "AsyncClient", FakeClient)
    client = TestClient(app_module.app)

    missing = client.post("/api/session", json={"context": {}})
    assert missing.status_code == 400
    assert missing.json()["detail"]["errors"][0]["field"] == "nome"
    assert FakeClient.last_json is None

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    created = client.post("/api/session", json={"context": {"nome": "Ana"}})
    assert created.status_code == 200
    payload = created.json()
    assert payload["client_secret"] == "ek_test"
    assert payload["webrtc"]["data_channel"] == "oai-events"
    assert "nome = Ana" in FakeClient.last_json["session"]["instructions"]
    assert FakeClient.last_json["session"]["max_output_tokens"] == 300


def test_response_returns_the_whole_text(monkeypatch):
    monkeypatch.setattr(app_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = TestClient(app_module.app)

    empty = client.post("/api/response", json={"context": {"nome": "Ana"}, "message": "  "})
    assert empty.status_code == 400

    created = client.post(
        "/api/response",
        json={
            "context": {"nome": "Ana"},
            "message": "Oi",
            "history": [{"role": "user", "content": "Tudo bem?"}],
        },
    )
    assert created.status_code == 200
    assert created.json()["text"] == "Olá, Ana."
    sent = FakeClient.last_json
    assert sent["stream"] is False
    assert sent["model"] == "gpt-6-astra"
    assert sent["max_output_tokens"] == 300
    assert sent["input"][-1] == {"role": "user", "content": "Oi"}
    assert "nome = Ana" in sent["instructions"]
    assert "Substitua este bloco" not in json.dumps(created.json(), ensure_ascii=False)


def test_missing_key_is_a_controlled_error():
    client = TestClient(app_module.app)
    response = client.post("/api/response", json={"context": {"nome": "Ana"}, "message": "Oi"})
    assert response.status_code == 503
    assert "sk-" not in response.text
