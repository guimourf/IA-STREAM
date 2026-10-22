from guard import decide, parse_classifier_output, refusal_instructions


def test_classifier_words():
    assert parse_classifier_output("fora") == "fora"
    assert parse_classifier_output("Fora.") == "fora"
    assert parse_classifier_output("outside, definitely") == "fora"
    assert parse_classifier_output("dentro") == "dentro"
    assert parse_classifier_output("") == "dentro"
    assert parse_classifier_output("talvez") == "dentro"


def test_moderation_blocks_before_scope():
    decision = decide(
        moderation_flagged=True,
        classifier="dentro",
        refusal_message="Volte ao tema.",
        moderation_refusal="Não posso ajudar com esse pedido.",
    )
    assert decision["allowed"] is False
    assert decision["reason"] == "moderation"
    assert "Não posso ajudar com esse pedido." in decision["refusal_instructions"]


def test_scope_block_and_fail_open():
    blocked = decide(
        moderation_flagged=False,
        classifier="fora",
        refusal_message="Desculpe,\nisso está fora.",
        moderation_refusal="Não.",
    )
    assert blocked["reason"] == "scope"
    assert "Desculpe, isso está fora." in blocked["refusal_instructions"]
    assert "\n\n" not in refusal_instructions("linha\n\nquebrada")

    open_decision = decide(
        moderation_flagged=None,
        classifier=None,
        refusal_message="Volte ao tema.",
        moderation_refusal="Não.",
    )
    assert open_decision["allowed"] is True
    assert open_decision["refusal_instructions"] is None
