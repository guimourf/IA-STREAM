"""Síntese da resposta completa.

O texto já veio da Responses API. Este módulo só pede o áudio correspondente.
"""

from __future__ import annotations


SPEECH_URL = "https://api.openai.com/v1/audio/speech"
MAX_SPEECH = 4096


class SpeechInputError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def build_speech_payload(assistant: dict, text: str) -> dict:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise SpeechInputError("Não há texto para falar.")
    if len(cleaned) > MAX_SPEECH:
        cleaned = cleaned[:MAX_SPEECH]
    return {
        "model": assistant.get("speech_model") or "tts-1",
        "voice": assistant.get("speech_voice") or "nova",
        "input": cleaned,
        "response_format": "mp3",
    }
