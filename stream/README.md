# Exemplo Stream

A resposta chega aos poucos. O áudio toca enquanto é gerado e o texto da fala cresce por eventos.

Este servidor só cria a sessão. O microfone e o alto-falante ficam no projeto que copiar o cliente.

## Arquivos

| Arquivo | Papel |
|---|---|
| `stream/session.py` | Endereços da OpenAI usados pelo cliente |
| `stream/voice.js` | WebRTC, microfone e transcrição em pedaços |
| `prompting.py` | Monta o prompt e a sessão Realtime, com `model`, voz e `max_output_tokens` |
| `POST /api/session` em `app.py` | Troca a chave permanente por um token efêmero |

## O que copiar

1. `assistant.json` e `prompting.py`.
2. `stream/session.py` e a rota `POST /api/session`.
3. `stream/voice.js`. A função `connect` é o stream. O restante da página de exemplo pode ser trocado pela interface do outro projeto.

## Fluxo

1. O cliente envia o contexto para `POST /api/session`.
2. O servidor devolve `client_secret` e `webrtc`.
3. O cliente abre o microfone, cria a oferta SDP e envia para `webrtc.url` com `Authorization: Bearer <client_secret>`.
4. O canal `oai-events` entrega os eventos. O texto da assistente vem em `response.output_audio_transcript.delta`.

`guard.enabled` fica desligado. Ligado, a resposta automática para e o `voice.js` chama `POST /api/guard` antes de pedir a fala.
