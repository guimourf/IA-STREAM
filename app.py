"""Exemplo de conversa por voz em stream.

O servidor só cria a sessão. O áudio vai e volta direto entre o navegador e a
OpenAI, pelo WebRTC implementado em static/js/voice.js. Copie os dois lados
para o projeto que for ter a conversa.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
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


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("ia_stream")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
ASSISTANT_PATH = BASE_DIR / "assistant.json"
OPENAI_CLIENT_SECRET_URL = "https://api.openai.com/v1/realtime/client_secrets"
WEBRTC_CALLS_URL = "https://api.openai.com/v1/realtime/calls"


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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Exemplo de conversa IA-STREAM...")
    try:
        assistant = load_assistant(ASSISTANT_PATH)
        logger.info("Assistente carregado: %s. guarda=%s", assistant["name"], assistant["guard"]["enabled"])
    except ConfigError as exc:
        logger.error("assistant.json inválido na subida: %s", exc)
    try:
        load_openai_api_key(CONFIG_PATH)
        logger.info("Chave OpenAI carregada no backend.")
    except ConfigError as exc:
        logger.warning("A conversa fica indisponível até configurar a chave: %s", exc)
    yield


app = FastAPI(title="IA-STREAM exemplo", lifespan=lifespan)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/api/assistant")
async def assistant_for_example() -> dict:
    """Dados que a tela de exemplo precisa. O prompt continua só no servidor."""
    return public_assistant(_load_assistant_or_http())


@app.post("/api/session")
async def create_session(request: Request) -> dict:
    """Cria o token da sessão. O stream de áudio começa depois, no voice.js."""
    logger.info("Exemplo pediu uma sessão Realtime.")
    assistant = _load_assistant_or_http()
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Dados inválidos. Envie o contexto em JSON.") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Dados inválidos. Envie o contexto em JSON.")

    try:
        context = normalize_context(assistant, body.get("context", {}))
    except ContextError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": exc.errors[0]["message"], "errors": exc.errors},
        ) from exc

    instructions = build_instructions(assistant, context)
    payload = build_session_payload(assistant, instructions)
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
        "Sessão de exemplo criada. session_id=%s campos_de_contexto=%s guarda=%s",
        session.get("id"),
        len(context),
        assistant["guard"]["enabled"],
    )
    return {
        "client_secret": client_secret,
        "expires_at": expires_at,
        "session_id": session.get("id"),
        "guard_enabled": assistant["guard"]["enabled"],
        "webrtc": {
            "url": WEBRTC_CALLS_URL,
            "content_type": "application/sdp",
            "data_channel": "oai-events",
        },
    }


@app.post("/api/guard")
async def guard_turn(request: Request) -> dict:
    """Usado pelo exemplo só quando guard.enabled está ligado no assistant.json."""
    assistant = _load_assistant_or_http()
    if not assistant["guard"]["enabled"]:
        return {"allowed": True, "reason": None, "refusal_instructions": None}
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Envie o texto da fala em JSON.") from exc
    text = body.get("text") if isinstance(body, dict) else None
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="Envie o texto da fala.")
    return await evaluate_utterance(assistant, text, _load_api_key_or_http())
