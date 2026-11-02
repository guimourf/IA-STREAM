# Exemplo Response

A resposta volta inteira. O cliente espera o fim da geração e só então mostra o texto. Não há áudio nem eventos parciais.

## Arquivos

| Arquivo | Papel |
|---|---|
| `response/complete.py` | Monta o corpo com `stream: false` e lê o texto final |
| `response/chat.js` | Envia a mensagem e mostra a resposta quando ela chega |
| `prompting.py` | O mesmo prompt do exemplo Stream, com o modelo de `response_model` |
| `POST /api/response` em `app.py` | Faz a chamada à OpenAI e devolve `{ "text": "..." }` |

## O que copiar

1. `assistant.json` e `prompting.py`.
2. `response/complete.py` e a rota `POST /api/response`.
3. `response/chat.js`, se o outro projeto for uma página. Um backend pode chamar a rota direto.

## Fluxo

1. O cliente envia `context`, `message` e, nas próximas falas, `history`.
2. O servidor coloca o prompt em `instructions` e a conversa em `input`.
3. A OpenAI responde em um único JSON, com `stream` desligado.
4. `extract_output_text` junta os trechos `output_text`. Não use só `output[0]`, porque a lista pode trazer outros itens.

`response_model` em `assistant.json` define o modelo. Troque se a conta não tiver o valor de exemplo.

O histórico aceita até 12 mensagens anteriores, cada uma com `role` `user` ou `assistant` e `content` em texto.
