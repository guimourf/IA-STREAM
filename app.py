"""Página de exemplo com três formatos separados.

Stream: a pasta stream/ abre a voz por WebRTC e a resposta chega aos poucos.
Response: a pasta response/ envia uma mensagem e recebe o texto inteiro.
Híbrido: a pasta hybrid/ ouve a voz, pede o texto inteiro e depois fala esse texto.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from guard import evaluate_utterance
from prompting import (
    ConfigError,
    ContextError,
    build_instructions,
    build_session_payload,
    load_assistant,
    load_openai_api_key,
    normalize_context,
    public_assistant,
)
from hybrid.speech import SPEECH_URL, SpeechInputError, build_speech_payload
from response.complete import (
    RESPONSES_URL,
    ResponseInputError,
    build_response_payload,
    extract_output_text,
)
from stream.session import OPENAI_CLIENT_SECRET_URL, webrtc_client_hint


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("ia_stream")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
ASSISTANT_PATH = BASE_DIR / "assistant.json"


def _load_assistant_or_http() -> dict:
    try:
        return load_assistant(ASSISTANT_PATH)
    except ConfigError as exc:
        logger.error("assistant.json inválido: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="O assistente está mal configurado. Revise o assistant.json.",
        ) from exc


def _load_api_key_or_http() -> str:
    try:
        return load_openai_api_key(CONFIG_PATH)
    except ConfigError as exc:
        logger.warning("Chave OpenAI indisponível: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="A conversa ainda não está configurada. Defina a chave da OpenAI no servidor.",
        ) from exc


def _read_json_object(body: object) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Dados inválidos. Envie um objeto JSON.")
    return body


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Dados inválidos. Envie um objeto JSON.") from exc
    return _read_json_object(body)


def _context_from(body: dict, assistant: dict) -> dict[str, str]:
    try:
        return normalize_context(assistant, body.get("context", {}))
    except ContextError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": exc.errors[0]["message"], "errors": exc.errors},
        ) from exc


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Exemplos Stream, Response e Voz + texto...")
    try:
        assistant = load_assistant(ASSISTANT_PATH)
        logger.info("Assistente carregado: %s", assistant["name"])
    except ConfigError as exc:
        logger.error("assistant.json inválido na subida: %s", exc)
    try:
        load_openai_api_key(CONFIG_PATH)
        logger.info("Chave OpenAI carregada no backend.")
    except ConfigError as exc:
        logger.warning("A conversa fica indisponível até configurar a chave: %s", exc)
    yield


app = FastAPI(title="IA-STREAM exemplos", lifespan=lifespan)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/stream", StaticFiles(directory=str(BASE_DIR / "stream")), name="stream_files")
app.mount("/response", StaticFiles(directory=str(BASE_DIR / "response")), name="response_files")
app.mount("/hybrid", StaticFiles(directory=str(BASE_DIR / "hybrid")), name="hybrid_files")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/api/assistant")
async def assistant_for_example() -> dict:
    """Dados da tela. O prompt continua só no servidor."""
    return public_assistant(_load_assistant_or_http())


@app.post("/api/session")
async def create_session(request: Request) -> dict:
    """Cria o token da sessão de voz. Com transcribe_only, a sessão só ouve."""
    assistant = _load_assistant_or_http()
    body = await _json_body(request)
    transcribe_only = bool(body.get("transcribe_only"))
    logger.info("Sessão de voz pedida. transcribe_only=%s", transcribe_only)
    context = _context_from(body, assistant)
    instructions = build_instructions(assistant, context)
    payload = build_session_payload(assistant, instructions, transcribe_only=transcribe_only)
    api_key = _load_api_key_or_http()

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                OPENAI_CLIENT_SECRET_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.RequestError as exc:
        logger.exception("Erro de rede ao solicitar token efêmero.")
        raise HTTPException(
            status_code=502,
            detail="Falha de conexão com o serviço de voz. Tente novamente.",
        ) from exc

    if response.status_code >= 400:
        logger.error("OpenAI retornou erro ao criar token efêmero: status=%s", response.status_code)
        raise HTTPException(
            status_code=502,
            detail="Não foi possível iniciar a conversa agora. Tente novamente em instantes.",
        )

    try:
        data = response.json()
    except Exception as exc:
        logger.error("Resposta da OpenAI sem JSON.")
        raise HTTPException(
            status_code=502,
            detail="Resposta inesperada do serviço de voz. Tente novamente.",
        ) from exc

    client_secret = data.get("value") or (data.get("client_secret") or {}).get("value")
    expires_at = data.get("expires_at")
    if expires_at is None and isinstance(data.get("client_secret"), dict):
        expires_at = data.get("client_secret", {}).get("expires_at")
    session = data.get("session") if isinstance(data.get("session"), dict) else {}
    if not client_secret:
        logger.error("Resposta sem client_secret válido.")
        raise HTTPException(
            status_code=500,
            detail="Resposta inesperada do serviço de voz. Tente novamente.",
        )

    logger.info(
        "Sessão de voz criada. session_id=%s transcribe_only=%s campos=%s",
        session.get("id"),
        transcribe_only,
        len(context),
    )
    return {
        "client_secret": client_secret,
        "expires_at": expires_at,
        "session_id": session.get("id"),
        "guard_enabled": assistant["guard"]["enabled"],
        "transcribe_only": transcribe_only,
        "webrtc": webrtc_client_hint(),
    }


@app.post("/api/response")
async def create_complete_response(request: Request) -> dict:
    """Exemplo Response: devolve o texto inteiro numa resposta só."""
    logger.info("Exemplo Response pediu uma resposta completa.")
    assistant = _load_assistant_or_http()
    body = await _json_body(request)
    context = _context_from(body, assistant)
    message = body.get("message")
    if not isinstance(message, str):
        raise HTTPException(status_code=400, detail="Escreva uma mensagem antes de enviar.")
    try:
        payload = build_response_payload(assistant, build_instructions(assistant, context), message, body.get("history"))
    except ResponseInputError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    api_key = _load_api_key_or_http()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                RESPONSES_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.RequestError as exc:
        logger.exception("Erro de rede ao pedir a resposta completa.")
        raise HTTPException(
            status_code=502,
            detail="Falha de conexão com o serviço de texto. Tente novamente.",
        ) from exc

    if response.status_code >= 400:
        logger.error("OpenAI retornou erro na resposta completa: status=%s", response.status_code)
        raise HTTPException(
            status_code=502,
            detail="Não foi possível responder agora. Tente novamente em instantes.",
        )

    try:
        data = response.json()
    except Exception as exc:
        logger.error("Resposta da OpenAI sem JSON.")
        raise HTTPException(
            status_code=502,
            detail="Resposta inesperada do serviço de texto. Tente novamente.",
        ) from exc

    text = extract_output_text(data if isinstance(data, dict) else {})
    if not text:
        logger.error("Resposta completa sem texto.")
        raise HTTPException(status_code=502, detail="A resposta veio vazia. Tente novamente.")

    logger.info("Resposta completa criada. response_id=%s", data.get("id") if isinstance(data, dict) else None)
    return {"text": text, "response_id": data.get("id") if isinstance(data, dict) else None}


@app.post("/api/speech")
async def create_speech(request: Request) -> Response:
    """Exemplo híbrido: fala o texto inteiro que já veio do Response."""
    logger.info("Exemplo híbrido pediu a voz da resposta.")
    assistant = _load_assistant_or_http()
    body = await _json_body(request)
    text = body.get("text")
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="Envie o texto para falar.")
    try:
        payload = build_speech_payload(assistant, text)
    except SpeechInputError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    api_key = _load_api_key_or_http()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                SPEECH_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.RequestError as exc:
        logger.exception("Erro de rede ao pedir a voz da resposta.")
        raise HTTPException(
            status_code=502,
            detail="Falha de conexão com o serviço de voz. Tente novamente.",
        ) from exc

    if response.status_code >= 400:
        logger.error("OpenAI retornou erro na síntese de voz: status=%s", response.status_code)
        raise HTTPException(
            status_code=502,
            detail="Não foi possível falar a resposta agora. Tente novamente em instantes.",
        )

    audio = response.content
    if not audio:
        logger.error("Síntese de voz sem áudio.")
        raise HTTPException(status_code=502, detail="A voz veio vazia. Tente novamente.")

    logger.info("Voz da resposta criada. bytes=%s", len(audio))
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/guard")
async def guard_turn(request: Request) -> dict:
    """Usado pelo exemplo Stream só quando guard.enabled está ligado."""
    assistant = _load_assistant_or_http()
    if not assistant["guard"]["enabled"]:
        return {"allowed": True, "reason": None, "refusal_instructions": None, "refusal_text": None}
    body = await _json_body(request)
    text = body.get("text")
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="Envie o texto da fala.")
    return await evaluate_utterance(assistant, text, _load_api_key_or_http())
