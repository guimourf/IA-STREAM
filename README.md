# IA-STREAM

API de conversa por voz para outros projetos. Este serviço guarda o prompt, monta a sessão da OpenAI Realtime e devolve um token efêmero. A interface fica no sistema que chama a API.

## Configurar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

- `openai.api_key` ou `OPENAI_API_KEY`: chave da OpenAI. Não sai deste servidor.
- `service_token` ou `SERVICE_TOKEN`: segredo que os outros projetos enviam em `Authorization: Bearer`. Sem ele, as rotas `/v1` ficam abertas.

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

O contrato interativo fica em `http://127.0.0.1:8000/docs`.

## Prompt

Edite `assistant.json`.

- `prompt.role`, `prompt.scope`, `prompt.out_of_scope`, `prompt.safety`, `prompt.style`, `prompt.language` e `prompt.extra` viram blocos das instruções.
- `prompt.instructions`, se preenchido, substitui esses blocos.
- `context_fields` é o que o outro projeto envia em `context`. Os valores entram no prompt como dados internos.
- `max_output_tokens` limita cada fala. O padrão é 300.
- `cors_origins` libera origens de navegador. Deixe vazio quando quem chama é outro backend.
- `guard.enabled` liga moderação e classificador de tema. O padrão é desligado. Com a guarda ligada, a resposta automática da detecção de fala fica desligada: o cliente manda cada transcrição para `/v1/guard` e só então pede a resposta.

Troque o escopo de exemplo antes de usar em público.

## Uso

```bash
curl http://127.0.0.1:8000/v1/assistant

curl -X POST http://127.0.0.1:8000/v1/realtime/sessions \
  -H "Authorization: Bearer $SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"context": {"nome": "Ana"}}'
```

A resposta traz `client_secret`, `expires_at`, `session_id`, `guard_enabled` e `webrtc`. O outro projeto abre a conexão de voz com a URL de `webrtc`, método POST, corpo SDP e cabeçalho `Authorization: Bearer <client_secret>`. O canal de dados se chama `oai-events`.

Se `guard_enabled` for verdadeiro, a cada transcrição:

```bash
curl -X POST http://127.0.0.1:8000/v1/guard \
  -H "Authorization: Bearer $SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "texto transcrito"}'
```

`allowed: false` vem com `refusal_instructions` para uma resposta que só diz a recusa. Falha dessa checagem não deve cortar a conversa.

`GET /health` responde sem credencial.

## Fora desta versão

Prompt salvo no painel da OpenAI e uma conexão de controle no servidor. O texto versionado aqui tem o mesmo efeito no modelo. As instruções vão na criação do token; um cliente com acesso à sessão ainda pode tentar alterá-las depois.
