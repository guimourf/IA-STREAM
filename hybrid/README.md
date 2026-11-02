# Exemplo Voz + texto

O usuário fala. A resposta da IA volta inteira: primeiro o JSON de texto, depois a voz desse mesmo texto.

A sessão Realtime só transcreve. Quem responde é a pasta `response/`. Quem fala o texto é `POST /api/speech`.

## Arquivos

| Arquivo | Papel |
|---|---|
| `hybrid/listen.js` | Microfone, transcrição, chamada ao Response e reprodução do áudio |
| `hybrid/speech.py` | Monta o corpo da síntese de voz |
| `stream/session.py` | Token WebRTC, com `transcribe_only` |
| `response/complete.py` | Texto inteiro, com `stream: false` |
| `POST /api/session` | Sessão que ouve e não responde |
| `POST /api/response` | Texto completo |
| `POST /api/speech` | MP3 da resposta |

## O que copiar

1. `assistant.json` e `prompting.py`.
2. `stream/session.py` e a rota `POST /api/session` com `transcribe_only: true`.
3. `response/complete.py` e a rota `POST /api/response`.
4. `hybrid/speech.py` e a rota `POST /api/speech`.
5. `hybrid/listen.js`.

## Fluxo

1. O cliente pede a sessão com `{ "context": {...}, "transcribe_only": true }`.
2. `create_response` fica desligado. A OpenAI só devolve a transcrição.
3. O cliente envia essa transcrição para `POST /api/response`.
4. A tela mostra `text` de uma vez.
5. O cliente envia o mesmo texto para `POST /api/speech` e toca o MP3.

`speech_model` e `speech_voice` em `assistant.json` configuram a fala. O padrão é `tts-1` e `nova`. A voz do Stream (`voice`) continua valendo só para o modo Stream.
