"""Endereços do stream de voz.

O navegador usa o token efêmero para abrir o WebRTC direto com a OpenAI.
Este módulo não recebe o áudio.
"""

OPENAI_CLIENT_SECRET_URL = "https://api.openai.com/v1/realtime/client_secrets"
WEBRTC_CALLS_URL = "https://api.openai.com/v1/realtime/calls"


def webrtc_client_hint() -> dict:
    return {
        "url": WEBRTC_CALLS_URL,
        "content_type": "application/sdp",
        "data_channel": "oai-events",
    }
