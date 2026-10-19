"""Normalização: variações convergem para a mesma forma."""

from jarvis.command_engine.normalizer import normalize


def test_basic():
    assert normalize("Abra o Navegador.") == "abrir o navegador"
    assert normalize("  ABRA   O NAVEGADOR  ") == "abrir o navegador"


def test_accents_and_punctuation():
    assert normalize("Que horas são?") == "que horas sao"
    assert normalize("J.A.R.V.I.S., abra meu navegador!") == "j a r v i s abrir meu navegador"


def test_verb_lemmatization():
    assert normalize("abre o navegador") == normalize("abra o navegador")
    assert normalize("minimize a janela") == "minimizar a janela"
    assert normalize("desligue o computador") == "desligar o computador"
    assert normalize("me diga as horas") == "me dizer as horas"


def test_none_and_empty():
    assert normalize(None) == ""
    assert normalize("") == ""
    assert normalize("   ") == ""


def test_variants_converge():
    variants = ["Abra o navegador.", "abra o navegador", "ABRA O NAVEGADOR",
                "  abra  o   navegador! "]
    assert len({normalize(v) for v in variants}) == 1


def test_preserves_important_words():
    out = normalize("abra o discord")
    assert "discord" in out
    assert "abrir" in out
