import json
from pathlib import Path

import pytest

from prompting import (
    ConfigError,
    ContextError,
    build_instructions,
    build_session_payload,
    load_assistant,
    normalize_context,
    public_assistant,
)


ROOT = Path(__file__).resolve().parents[1]


def _assistant(**overrides):
    base = load_assistant(ROOT / "assistant.json")
    base.update(overrides)
    return base


def test_shipped_assistant_builds_separated_blocks():
    assistant = load_assistant(ROOT / "assistant.json")
    text = build_instructions(assistant, {"nome": "Ana"})

    assert "# Papel\n" in text
    assert "# Escopo\n" in text
    assert "# Fora do escopo\n" in text
    assert "# Segurança\n" in text
    assert "# Estilo de fala\n" in text
    assert "# Idioma\n" in text
    assert "# Regras fixas\n" in text
    assert "# Contexto interno\nnome = Ana" in text
    assert "sentindo.Fale" not in text
    assert "\n\n# Escopo\n" in text
    assert "formulários" in text


def test_custom_instructions_replace_blocks_and_keep_fixed_rules():
    assistant = _assistant()
    assistant["prompt"] = dict(assistant["prompt"])
    assistant["prompt"]["instructions"] = "Fale como um recepcionista."
    text = build_instructions(assistant, {})

    assert text.startswith("Fale como um recepcionista.")
    assert "# Papel" not in text
    assert "# Regras fixas" in text
    assert "# Contexto interno" not in text


def test_session_limits_tokens_and_guard_disables_auto_response():
    assistant = _assistant()
    payload = build_session_payload(assistant, "oi")
    session = payload["session"]

    assert session["max_output_tokens"] == 300
    assert session["model"] == "gpt-realtime-2.1"
    assert session["audio"]["output"]["voice"] == "marin"
    assert session["audio"]["input"]["turn_detection"]["create_response"] is True

    assistant["guard"] = dict(assistant["guard"], enabled=True)
    guarded = build_session_payload(assistant, "oi")
    assert guarded["session"]["audio"]["input"]["turn_detection"]["create_response"] is False


def test_public_config_hides_the_prompt():
    assistant = load_assistant(ROOT / "assistant.json")
    public = public_assistant(assistant)

    assert public["context_fields"][0]["key"] == "nome"
    blob = json.dumps(public, ensure_ascii=False)
    assert "Substitua este bloco" not in blob
    assert "Regras fixas" not in blob
    assert "instructions" not in blob


def test_required_context_and_cleanup(tmp_path: Path):
    path = tmp_path / "assistant.json"
    path.write_text(
        json.dumps(
            {
                "prompt": {"role": "Você atende pessoas."},
                "context_fields": [
                    {"key": "nome", "label": "Nome", "type": "text", "required": True, "max_length": 20},
                    {
                        "key": "idade",
                        "label": "Idade",
                        "type": "number",
                        "required": True,
                        "min": 1,
                        "max": 120,
                    },
                    {
                        "key": "turno",
                        "label": "Turno",
                        "type": "select",
                        "required": False,
                        "options": [
                            {"value": "manha", "label": "Manhã"},
                            {"value": "tarde", "label": "Tarde"},
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    assistant = load_assistant(path)

    with pytest.raises(ContextError) as empty:
        normalize_context(assistant, {})
    assert empty.value.errors[0]["field"] == "nome"

    with pytest.raises(ContextError) as age:
        normalize_context(assistant, {"nome": "Ana", "idade": "130"})
    assert age.value.errors[0]["field"] == "idade"

    values = normalize_context(
        assistant,
        {"nome": "  Ana   Maria  ", "idade": "34", "turno": "manha"},
    )
    assert values == {"nome": "Ana Maria", "idade": "34", "turno": "manha"}

    text = build_instructions(assistant, values)
    assert "nome = Ana Maria\nidade = 34\nturno = manha" in text


def test_invalid_assistant_is_rejected(tmp_path: Path):
    path = tmp_path / "assistant.json"
    path.write_text('{"prompt": {}}', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_assistant(path)

    path.write_text('{"prompt": {"role": "Oi"}, "max_output_tokens": 9000}', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_assistant(path)
