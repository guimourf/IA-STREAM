# IA-STREAM

Conversa por voz genérica. O programador define o contexto em `assistant.json`. O servidor monta a sessão da OpenAI Realtime e entrega ao navegador só um token efêmero.

## Configurar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Coloque a chave em `config.json` (`openai.api_key`) ou na variável `OPENAI_API_KEY`. A chave não vai para o navegador.

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Onde editar o prompt

Edite `assistant.json`.

- `prompt.role`, `prompt.scope`, `prompt.out_of_scope`, `prompt.safety`, `prompt.style`, `prompt.language` e `prompt.extra` viram blocos separados nas instruções da sessão.
- `prompt.instructions`, se preenchido, substitui esses blocos.
- `context_fields` desenha o formulário de antes da conversa. Os valores entram no final do prompt como dados internos. O navegador não recebe o texto do prompt.
- `max_output_tokens` limita o tamanho de cada fala. O padrão é 300.
- `guard.enabled` liga uma checagem extra, desligada por padrão. Com ela ligada, a resposta automática da detecção de fala é desativada: cada transcrição passa por moderação e, se houver escopo, por um classificador. Fora do escopo, a voz diz só a frase de recusa configurada. Falha de rede nessa checagem não corta a conversa.

O arquivo de exemplo já traz um escopo provisório. Troque esse texto pelo assunto real antes de usar em público.

## O que fica de fora de propósito

O prompt versionado no painel da OpenAI e uma conexão de controle no servidor não entram nesta versão. O efeito do prompt no modelo é o mesmo se o texto sair daqui, e a conexão extra mudaria a arquitetura sem ser necessária para um totem fechado. As instruções vão na criação do token, mas alguém com o DevTools ainda pode tentar um `session.update` depois de conectar.
