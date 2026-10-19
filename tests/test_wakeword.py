"""Wake word: detectar SEM descartar o comando restante (crítico)."""

from jarvis.voice.wakeword import detect


def test_jarvis_with_dots_and_comma():
    r = detect("J.A.R.V.I.S., abra o navegador.")
    assert r.detected is True
    assert r.command_text == "abra o navegador."


def test_jarvis_plain():
    r = detect("jarvis abra o navegador")
    assert r.detected is True
    assert r.command_text == "abra o navegador"


def test_jarvis_capitalized():
    r = detect("Jarvis que horas são?")
    assert r.detected is True
    assert "que horas" in r.command_text


def test_no_wake_word():
    r = detect("abra o navegador")
    assert r.detected is False
    assert r.command_text == "abra o navegador"


def test_wake_only_dots():
    r = detect("J.A.R.V.I.S.")
    assert r.detected is True
    assert r.command_text == ""


def test_wake_only_comma():
    r = detect("J.A.R.V.I.S.,")
    assert r.detected is True
    assert r.command_text == ""


def test_command_never_discarded():
    """O erro crítico seria detectar a wake e perder o comando."""
    for raw in ["JARVIS abra a calculadora",
                "J.A.R.V.I.S., que horas são?",
                "jarvis, desligue o computador"]:
        r = detect(raw)
        assert r.detected is True
        assert len(r.command_text) > 3, raw


def test_empty_and_none():
    assert detect("") == detect("", )
    assert detect(None).detected is False
    assert detect("   ").command_text == ""
