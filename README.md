# IA-STREAM

Exemplo de conversa por voz em stream para copiar em outro projeto. O áudio não passa por este servidor: ele cria a sessão e o navegador fala direto com a OpenAI.

## Rodar o exemplo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Coloque a chave em `config.json` (`openai.api_key`) ou na variável `OPENAI_API_KEY`.

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Abra `http://127.0.0.1:8000`, preencha o nome e inicie a conversa. A resposta falada toca enquanto é gerada. O texto correspondente aparece em pedaços na tela.

## O que copiar

- `assistant.json`: o prompt. Edite `prompt.role`, `scope`, `out_of_scope`, `safety`, `style`, `language` e `extra`. Se preencher `prompt.instructions`, esse texto substitui os blocos. `context_fields` são os dados pedidos antes da conversa.
- `prompting.py`: junta esses blocos, valida o contexto e monta a sessão, inclusive o `max_output_tokens`.
- `app.py`: a rota `POST /api/session`, que troca a chave permanente por um token efêmero. A chave fica no servidor.
- `static/js/voice.js`: o stream. Pede o token, abre o microfone, conecta o WebRTC e mostra a transcrição conforme os eventos `response.output_audio_transcript.delta` chegam.

`guard.enabled` fica desligado. Ligado, a resposta automática para e o `voice.js` consulta `POST /api/guard` antes de pedir a fala.

Troque o escopo de exemplo antes de usar o texto em público.
