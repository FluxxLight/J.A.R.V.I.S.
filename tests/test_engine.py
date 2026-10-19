"""Command Engine: intenções, aliases, parâmetros, desconhecidos."""

import pytest


@pytest.mark.parametrize("text", [
    "abra o navegador", "abrir navegador", "abre o navegador",
    "pode abrir o navegador", "inicia o navegador", "Abra o Navegador.",
    "ABRA O NAVEGADOR",
])
def test_open_browser_variants(engine, text):
    r = engine.process(text)
    assert r.intent == "OPEN_BROWSER", (text, r)
    assert r.success is True and r.executed is True
    assert r.action_id == "OpenApplication"


@pytest.mark.parametrize("text,intent", [
    ("abra a calculadora", "OPEN_CALCULATOR"),
    ("abre a calculadora", "OPEN_CALCULATOR"),
    ("abra o bloco de notas", "OPEN_NOTEPAD"),
    ("abra o explorador de arquivos", "OPEN_EXPLORER"),
    ("abra as configurações", "OPEN_SETTINGS"),
    ("que horas são?", "GET_TIME"),
    ("que horas sao", "GET_TIME"),
    ("me diga as horas", "GET_TIME"),
    ("que dia é hoje?", "GET_DATE"),
    ("minimize a janela", "MINIMIZE_WINDOW"),
    ("maximize a janela", "MAXIMIZE_WINDOW"),
    ("tela cheia", "TOGGLE_FULLSCREEN"),
    ("bloqueie o computador", "LOCK_COMPUTER"),
    ("ajuda", "HELP"),
])
def test_native_intents(engine, text, intent):
    r = engine.process(text)
    assert r.intent == intent, (text, r)
    assert r.success is True, (text, r)


def test_time_answer_format(engine):
    r = engine.process("que horas são?")
    assert "hora" in r.message.lower()
    assert r.speak_text != ""


def test_unknown_command(engine):
    r = engine.process("faca um bolo de chocolate")
    assert r.success is False
    assert r.intent == "UNKNOWN"


def test_empty_and_none(engine):
    assert engine.process("").success is False
    assert engine.process(None).success is False
    assert engine.process("   ").success is False


def test_open_url_with_address(engine):
    r = engine.process("abra o site https://example.com")
    assert r.intent == "OPEN_URL"
    assert r.params.get("url") == "https://example.com"
    assert r.success is True


def test_open_known_site(engine):
    r = engine.process("abra o youtube")
    assert r.intent == "OPEN_URL", r
    assert "youtube" in r.params.get("url", ""), r


def test_close_app(engine):
    r = engine.process("feche o discord")
    assert r.intent == "CLOSE_APP", r
    assert r.params.get("app") == "discord"
    assert r.success is True and r.executed is True  # dry-run simula


def test_close_app_needs_target(engine):
    r = engine.process("feche")
    assert r.intent == "CLOSE_APP"
    assert r.success is False
    assert "qual aplicativo" in r.message.lower()


def test_close_pronoun_without_context_asks(engine):
    r = engine.process("feche ele")
    assert r.success is False  # sem contexto: honesto, pede o alvo


def test_exit_wins_over_close(engine):
    r = engine.process("feche o jarvis")
    assert r.intent == "EXIT_JARVIS", r


def test_never_raises(engine):
    for weird in [None, "", " ", "x" * 1000, "!@#$%", "12345",
                  "çãõü ë", "\n\t", "J.A.R.V.I.S.,"]:
        r = engine.process(weird)
        assert r is not None
