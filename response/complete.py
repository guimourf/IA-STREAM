"""Chamada da Responses API com stream desligado.

A resposta HTTP só volta quando o texto inteiro está pronto.
"""

from __future__ import annotations


RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_MESSAGE = 4000
MAX_HISTORY = 12


class ResponseInputError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def build_response_payload(assistant: dict, instructions: str, message: str, history: object) -> dict:
    text = " ".join((message or "").split())
    if not text:
        raise ResponseInputError("Escreva uma mensagem antes de enviar.")
    if len(text) > MAX_MESSAGE:
        raise ResponseInputError(f"A mensagem pode ter no máximo {MAX_MESSAGE} caracteres.")

    payload = {
        "model": assistant["response_model"],
        "instructions": instructions,
        "input": _input_items(text, history),
        "stream": False,
    }
    limit = assistant.get("max_output_tokens")
    if isinstance(limit, int):
        payload["max_output_tokens"] = limit
    return payload


def _input_items(message: str, history: object) -> list[dict[str, str]]:
    if history is None:
        history = []
    if not isinstance(history, list):
        raise ResponseInputError("O histórico precisa ser uma lista.")
    if len(history) > MAX_HISTORY:
        raise ResponseInputError(f"Envie no máximo {MAX_HISTORY} mensagens anteriores.")

    items: list[dict[str, str]] = []
    for turn in history:
        if not isinstance(turn, dict):
            raise ResponseInputError("Cada item do histórico precisa ter papel e texto.")
        role = turn.get("role")
        content = turn.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            raise ResponseInputError("Cada item do histórico precisa ter papel e texto.")
        cleaned = " ".join(content.split())
        if not cleaned:
            continue
        if len(cleaned) > MAX_MESSAGE:
            raise ResponseInputError(f"Uma mensagem do histórico passa de {MAX_MESSAGE} caracteres.")
        items.append({"role": role, "content": cleaned})
    items.append({"role": "user", "content": message})
    return items


def extract_output_text(data: dict) -> str:
    shortcut = data.get("output_text")
    if isinstance(shortcut, str) and shortcut.strip():
        return shortcut.strip()
    parts: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                parts.append(content.get("text") or "")
    return "".join(parts).strip()
