import pytest

from response.complete import ResponseInputError, build_response_payload, extract_output_text


def test_extract_output_text_skips_non_message_items():
    text = extract_output_text(
        {
            "output": [
                {"type": "reasoning", "content": []},
                {"type": "message", "content": [{"type": "output_text", "text": "Primeira "}, {"type": "output_text", "text": "frase."}]},
            ]
        }
    )
    assert text == "Primeira frase."
    assert extract_output_text({"output_text": "Atalho"}) == "Atalho"


def test_history_must_be_a_short_list_of_turns():
    assistant = {"response_model": "gpt-6-astra", "max_output_tokens": 300}
    with pytest.raises(ResponseInputError):
        build_response_payload(assistant, "instruções", "Oi", {"role": "user"})

    payload = build_response_payload(
        assistant,
        "instruções",
        "Oi",
        [{"role": "assistant", "content": "Olá"}],
    )
    assert payload["stream"] is False
    assert payload["input"] == [
        {"role": "assistant", "content": "Olá"},
        {"role": "user", "content": "Oi"},
    ]
