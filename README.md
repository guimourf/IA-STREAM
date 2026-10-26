# IA-STREAM

Exemplo para copiar em outro projeto. A mesma assistente pode responder de três jeitos, e cada jeito está numa pasta.

| Modo | O que acontece | Pasta |
|---|---|---|
| Stream | A voz e o texto chegam aos poucos, direto da OpenAI | [`stream/`](stream/README.md) |
| Response | A mensagem vai ao servidor e o texto volta inteiro, num único JSON | [`response/`](response/README.md) |
| Voz + texto | O usuário fala; a resposta volta inteira, em texto e em voz | [`hybrid/`](hybrid/README.md) |

Na tela, os botões **Stream**, **Response** e **Voz + texto** trocam o modo. O prompt é o mesmo.

## Rodar

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

Abra `http://127.0.0.1:8000`.

## O que os modos compartilham

- `assistant.json`: o prompt em blocos (`role`, `scope`, `out_of_scope`, `safety`, `style`, `language`, `extra`). `prompt.instructions`, se preenchido, substitui os blocos. `context_fields` são os dados pedidos antes da conversa.
- `prompting.py`: junta o prompt, valida o contexto e limita o tamanho com `max_output_tokens`.
- `model` configura a voz do Stream. `response_model` configura o texto do Response e do Voz + texto. `speech_model` e `speech_voice` configuram a fala do Voz + texto.

Troque o escopo de exemplo antes de usar o texto em público. Troque `response_model` se a conta não tiver o modelo que veio no arquivo.

O passo a passo de cada modo está no README da pasta correspondente.
