import pytest

from hybrid.speech import SpeechInputError, build_speech_payload


def test_speech_payload_uses_complete_text_and_caps_length():
    assistant = {"speech_model": "tts-1", "speech_voice": "nova"}
    with pytest.raises(SpeechInputError):
        build_speech_payload(assistant, "   ")

    payload = build_speech_payload(assistant, "  Olá, Ana.  ")
    assert payload == {
        "model": "tts-1",
        "voice": "nova",
        "input": "Olá, Ana.",
        "response_format": "mp3",
    }

    long_text = "a" * 5000
    capped = build_speech_payload(assistant, long_text)
    assert len(capped["input"]) == 4096
