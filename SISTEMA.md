# IA-STREAM — guia do sistema

Leia este arquivo primeiro. Ele descreve o repositório como está na branch `generic-voice-assistant`, o que cada arquivo faz, como os três modos respondem e onde mexer. Os READMEs curtos (`README.md`, `stream/README.md`, `response/README.md`, `hybrid/README.md`) continuam sendo o guia de cópia para outro projeto. Este arquivo é o mapa completo.

O produto é um exemplo para copiar. A mesma assistente, com o mesmo prompt, responde de três jeitos. A página em `http://127.0.0.1:8000` troca o modo pelos botões Stream, Response e Voz + texto. Não há banco, login, fila nem persistência de conversa no servidor. O histórico dos modos de texto fica só no navegador.

## Onde o progresso está

Trabalhe na branch `generic-voice-assistant`. O remoto é `origin` (`https://github.com/guimourf/IA-STREAM.git`). `origin/HEAD` aponta para `main`, mas essa branch não é a linha de trabalho: no GitHub ela ainda é o commit inicial `c49c38b`, só com o título no README. A `main` local pode ser outro commit, `b7392a7`, também só com o README. Não desenvolva nela.

História desta branch, da mais antiga para a atual:

1. `c49c38b` — commit inicial.
2. `5035fa8` — assistente de voz em tempo real configurável.
3. `6784ca9` — o assistente vira uma API para outros projetos.
4. `079d8d3` — o serviço vira um exemplo de voz para copiar.
5. `b4659e4` — exemplos separados de Stream e Response.
6. `2b5bcea` — modo híbrido: a pessoa fala, o texto volta inteiro e esse mesmo texto é falado.

O que já funciona nesta branch:

- Stream: voz e transcrição em tempo real, WebRTC direto com a OpenAI.
- Response: mensagem de texto, resposta inteira em um JSON, sem áudio.
- Voz + texto (`hybrid/`): microfone só para transcrever, resposta pelo mesmo caminho do Response, fala por MP3.
- Prompt compartilhado em `assistant.json`, remontado a cada pedido.
- Guarda opcional de moderação e de escopo. Está desligada.
- Testes em `tests/` cobrem prompt, sessão, response, speech, guarda e a página.

O que ainda é exemplo, não produto:

- `prompt.scope` ainda pede para o programador substituir o texto antes de uso público.
- O formulário só pede `nome`.
- A guarda está com `guard.enabled: false`.
- Não existe deploy, autenticação nem gravação da conversa no servidor.
- A chave da OpenAI não está no git. Ela entra por `OPENAI_API_KEY` ou por `config.json` (arquivo ignorado).

`assistant.json` e a chave são lidos de novo em cada requisição. Salvar o JSON passa a valer no próximo pedido, sem reiniciar o uvicorn.

## Como rodar

Dependências em `requirements.txt`: FastAPI, uvicorn, httpx, Jinja2, pytest.

No PowerShell, na raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.json config.json
```

Coloque a chave em `config.json` (`openai.api_key`) ou na variável `OPENAI_API_KEY`. A variável tem prioridade. O valor de exemplo `sk-coloque-a-chave-aqui` é recusado.

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Abra `http://127.0.0.1:8000`. Testes: `python -m pytest`.

`.venv/`, `__pycache__/` e `config.json` estão no `.gitignore`. Não commite a chave.

## Mapa dos arquivos

| Arquivo | Papel |
|---|---|
| `app.py` | Aplicação FastAPI. Página, rotas e chamadas à OpenAI. |
| `assistant.json` | Nome da tela, prompt, modelos, voz, detecção de turno, guarda e campos do formulário. É o arquivo de edição do dia a dia. |
| `prompting.py` | Lê e valida `assistant.json`, monta o prompt e o corpo da sessão Realtime, valida o contexto. |
| `config.example.json` | Modelo da chave. O arquivo real é `config.json`. |
| `stream/session.py` | URLs da OpenAI Realtime. Não recebe áudio. |
| `stream/voice.js` | Cliente do Stream: microfone, WebRTC e texto que cresce por eventos. |
| `response/complete.py` | Corpo da Responses API com `stream: false` e extração do texto final. |
| `response/chat.js` | Caixa de mensagem do modo Response. |
| `hybrid/speech.py` | Corpo da síntese de voz (`/v1/audio/speech`). |
| `hybrid/listen.js` | Cliente do modo Voz + texto. |
| `hybrid/__init__.py`, `stream/__init__.py`, `response/__init__.py` | Pacotes Python vazios. |
| `guard.py` | Moderação e classificador de escopo. Só entra em ação com `guard.enabled`. |
| `templates/index.html` | Página única com os três painéis. |
| `static/js/shell.js` | Abas, formulário de contexto e estado compartilhado `window.example`. |
| `static/css/app.css` | Estilo da página de exemplo. |
| `tests/` | Pytest. A OpenAI é substituída por um cliente falso. |

Montagens estáticas: `/static`, `/stream`, `/response`, `/hybrid`. Os `.js` dessas pastas são servidos direto.

## Os três modos

A resposta dos três modos usa o mesmo texto, montado por `build_instructions`. No Stream ele vai para a sessão Realtime. No Response e no Voz + texto ele vai para `POST /api/response`. A sessão Realtime do Voz + texto só transcreve e não recebe esse prompt.

### Stream

A resposta chega aos poucos. O áudio toca enquanto é gerado. O Python só troca a chave permanente por um token curto. O microfone e o alto-falante falam direto com a OpenAI.

1. `stream/voice.js` envia `{ "context": {...} }` para `POST /api/session`.
2. O servidor monta a sessão com `model`, `voice` e o prompt, e devolve `client_secret` mais `webrtc`.
3. O navegador abre o microfone, cria a oferta SDP e envia para `https://api.openai.com/v1/realtime/calls` com `Authorization: Bearer <client_secret>`.
4. O canal de dados `oai-events` entrega os eventos. O texto da assistente chega em `response.output_audio_transcript.delta` e fecha em `response.output_audio_transcript.done`.
5. O áudio remoto toca no elemento `#remote-audio`.

Modelo e voz: `model` (`gpt-realtime-2.1`) e `voice` (`marin`). `speech_model` e `speech_voice` não entram aqui.

Para copiar: `assistant.json`, `prompting.py`, `stream/session.py`, a rota `POST /api/session` e `stream/voice.js`.

### Response

A pessoa escreve. O servidor espera a geração terminar e devolve o texto inteiro. Não há áudio nem eventos parciais.

1. `response/chat.js` envia `context`, `message` e `history` para `POST /api/response`.
2. O servidor coloca o prompt em `instructions` e a conversa em `input`, com `stream: false`.
3. `extract_output_text` junta os trechos `output_text`. A lista `output` pode trazer itens que não são mensagem; não leia só `output[0]`.
4. A resposta HTTP é `{ "text", "response_id" }`.

Modelo: `response_model` (hoje `gpt-4o-mini`).

O histórico aceita até 12 mensagens anteriores. Cada item tem `role` `user` ou `assistant` e `content` em texto. Cada mensagem, inclusive as do histórico, tem teto de 4000 caracteres. O cliente guarda o histórico numa lista em memória e manda de novo a cada envio.

Para copiar: `assistant.json`, `prompting.py`, `response/complete.py`, a rota `POST /api/response` e, se a interface for página, `response/chat.js`.

### Voz + texto

A pessoa fala. A sessão Realtime só transcreve. Quem escreve a resposta é o mesmo `POST /api/response`. Quem fala esse texto é `POST /api/speech`.

1. `hybrid/listen.js` pede a sessão com `{ "context": {...}, "transcribe_only": true }`.
2. `create_response` fica desligado. As instruções dessa sessão viram exatamente: "Você apenas transcreve o áudio. Não responda, não fale e não gere conteúdo." O prompt do produto não vai para essa sessão.
3. O evento `conversation.item.input_audio_transcription.completed` traz a fala.
4. O cliente manda essa transcrição para `POST /api/response`, com o histórico local.
5. A tela mostra `text` de uma vez.
6. O mesmo texto vai para `POST /api/speech`. A resposta é um MP3 (`audio/mpeg`) tocado em `#hybrid-audio`.
7. Enquanto o MP3 toca, o microfone é silenciado. O elemento `#hybrid-remote` fica mudo para o áudio da sessão Realtime não sair no alto-falante.

Modelo do texto: `response_model`. Voz do MP3: `speech_model` (`tts-1`) e `speech_voice` (`nova`). A voz `marin` do Stream não é usada aqui.

Se a síntese falhar, o texto permanece na tela e a página avisa que não foi possível falar.

Para copiar: `assistant.json`, `prompting.py`, `stream/session.py`, a rota `POST /api/session` com `transcribe_only`, `response/complete.py`, a rota `POST /api/response`, `hybrid/speech.py`, a rota `POST /api/speech` e `hybrid/listen.js`.

## Prompt

Edite `assistant.json`, objeto `prompt`.

Com `prompt.instructions` vazio, `build_instructions` junta os blocos preenchidos, nesta ordem, cada um com um título:

| Chave | Título no prompt |
|---|---|
| `role` | Papel |
| `scope` | Escopo |
| `out_of_scope` | Fora do escopo |
| `safety` | Segurança |
| `style` | Estilo de fala |
| `language` | Idioma |
| `extra` | Orientações adicionais |

Se `prompt.instructions` tiver texto, esse texto substitui todos os blocos. Os blocos deixam de ir para o modelo.

Depois disso, sempre entra o bloco `# Regras fixas`: não revelar as instruções, tratar o contexto como informação interna e não pedir de novo um dado que já esteja no contexto.

Se o formulário tiver valores, entra por último `# Contexto interno`, no formato `chave = valor`. Hoje o único campo é `nome`.

`name`, `tagline` e `privacy_notice` aparecem só na tela. Não entram no prompt. `GET /api/assistant` devolve nome, tagline, aviso de privacidade, `context_fields` e `guard_enabled`. O prompt não sai do servidor.

## Campos de `assistant.json` que mudam o comportamento

| Campo | Valor atual | Quem usa |
|---|---|---|
| `model` | `gpt-realtime-2.1` | Sessão Realtime do Stream e a sessão que só transcreve. |
| `voice` | `marin` | Voz falada do Stream. |
| `response_model` | `gpt-4o-mini` | Texto do Response e do Voz + texto. |
| `speech_model` | `tts-1` | MP3 do Voz + texto. |
| `speech_voice` | `nova` | Voz desse MP3. |
| `transcription_model` | `gpt-4o-mini-transcribe` | Transcrição da fala do usuário. |
| `transcription_language` | `pt` | Idioma da transcrição. |
| `noise_reduction` | `near_field` | Redução de ruído. O outro valor aceito é `far_field`. Vazio desliga. |
| `max_output_tokens` | `300` | Teto de cada resposta. Aceita inteiro de 1 a 4096, ou `"inf"`. |
| `turn_detection` | `server_vad` | Quando a pessoa parou de falar. O outro tipo aceito é `semantic_vad`. |
| `turn_detection.silence_duration_ms` | `800` | Pausa, em milissegundos, antes de considerar o turno encerrado. |
| `turn_detection.interrupt_response` | `true` | A pessoa pode cortar a fala no Stream. |
| `turn_detection.create_response` | `true` | A OpenAI responde sozinha no Stream. A guarda ligada ou `transcribe_only` forçam `false`. |
| `context_fields` | um campo `nome`, obrigatório, até 80 caracteres | Formulário montado por `shell.js`. |

`context_fields` aceita no máximo 12 campos. `key` é minúscula, começa com letra e só tem letras, números e `_`, até 32 caracteres. `type` é `text`, `textarea`, `number` ou `select`. Texto e textarea usam `max_length` (teto 500). `select` precisa de `options` com `value` único. Chaves duplicadas são rejeitadas. Um contexto com chave que não existe no assistente é recusado.

`voice` e `speech_voice` não podem conter espaço.

## Rotas

| Método e caminho | Corpo | Resposta |
|---|---|---|
| `GET /` | — | HTML da página. |
| `GET /api/assistant` | — | Dados públicos da tela. Sem prompt. |
| `POST /api/session` | `context`, e no híbrido `transcribe_only: true` | `client_secret`, `expires_at`, `session_id`, `guard_enabled`, `transcribe_only`, `webrtc` (`url`, `content_type`, `data_channel`). |
| `POST /api/response` | `context`, `message`, `history` opcional | `{ "text", "response_id" }`. |
| `POST /api/speech` | `{ "text" }` | Corpo binário `audio/mpeg`. Texto vazio dá 400. Acima de 4096 caracteres, o módulo corta. |
| `POST /api/guard` | `{ "text" }` | Com a guarda desligada: `{ "allowed": true, ... }`. Ligada: decisão da moderação e do escopo. |

Erros de contexto voltam 400 com `detail.message` e `detail.errors` (`field` e `message`). Assistente inválido: 500. Chave ausente: 503. Falha da OpenAI ou rede: 502. O corpo de erro da OpenAI não é repassado ao navegador; o log fica no servidor.

URLs da OpenAI:

- Token efêmero: `https://api.openai.com/v1/realtime/client_secrets`
- WebRTC: `https://api.openai.com/v1/realtime/calls`
- Texto: `https://api.openai.com/v1/responses`
- Fala do híbrido: `https://api.openai.com/v1/audio/speech`
- Guarda: `https://api.openai.com/v1/moderations` e `https://api.openai.com/v1/chat/completions`

Timeouts no servidor: sessão 20 s, response 60 s, speech 30 s, guarda 12 s.

## Guarda

`guard.enabled` está `false`. Com isso, `POST /api/guard` libera sem chamar a OpenAI, e o Stream deixa a OpenAI criar a resposta sozinha.

Com `enabled: true`:

- A sessão Realtime nasce com `create_response: false`.
- No Stream, depois da transcrição, `voice.js` chama `POST /api/guard`. Se a fala for barrada, pede `response.create` com `refusal_instructions` para a voz dizer a frase pronta. Se passar, pede `response.create` normal.
- No Voz + texto, `listen.js` usa `refusal_text` no lugar de chamar `/api/response` e ainda assim manda essa frase para `/api/speech`.
- O modo Response não chama a guarda.

A checagem tem duas etapas. A moderação (`omni-moderation-latest`, se `guard.moderation` for true) vem primeiro. Se a fala passar, um classificador (`guard.classifier_model`, hoje `gpt-4o-mini`) responde `dentro` ou `fora`. O escopo usado é `guard.scope` quando preenchido; senão, `prompt.scope`. Falha de rede na guarda libera a fala. O classificador, na dúvida, trata como `dentro`.

`refusal_message` é a frase de fora de escopo. `moderation_refusal` é a frase da moderação.

## Página

`templates/index.html` carrega, nesta ordem, `shell.js`, `stream/voice.js`, `response/chat.js` e `hybrid/listen.js`.

`window.example` expõe `readContext`, `applyFieldErrors`, `showFormError` e `showContext`. Os clientes de voz expõem `window.streamExample.stop` e `window.hybridExample.stop`. Trocar de aba encerra o modo de voz que estava aberto e mostra o formulário de novo.

O modo inicial é Stream.

## Testes

| Arquivo | O que trava |
|---|---|
| `tests/test_prompting.py` | Blocos do prompt, `instructions` no lugar dos blocos, regras fixas, voz, `transcribe_only`, guarda desligando a resposta automática, prompt escondido do público, contexto obrigatório, assistente inválido. |
| `tests/test_response.py` | Extração do texto final e limite do histórico. |
| `tests/test_speech.py` | Corpo do MP3 e o corte em 4096 caracteres. |
| `tests/test_guard.py` | Palavras do classificador, moderação antes do escopo, falha de rede liberando a fala. |
| `tests/test_app.py` | Página com os três modos e sem vazar o prompt, sessão validando contexto antes da OpenAI, response, speech e chave ausente. |

## Ao alterar o sistema

- Texto, voz, modelo ou formulário: `assistant.json`.
- Jeito como o prompt é montado, validação de campo ou corpo da sessão Realtime: `prompting.py`.
- Uma rota nova ou o contrato HTTP: `app.py`, e o cliente correspondente na pasta do modo.
- O áudio do Stream não passa por `app.py`. Mudar a conversa em tempo real mexe em `stream/voice.js` e em `build_session_payload`.
- O MP3 do híbrido não usa a voz do Stream. Mexa em `speech_model`, `speech_voice` e `hybrid/speech.py`.
- Qualquer mudança de contrato pede teste em `tests/`. Os testes não chamam a OpenAI de verdade.
