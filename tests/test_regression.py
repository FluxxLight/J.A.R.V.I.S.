"""Regressão: texto==voz, customs intactos, aliases/contexto/storage ok."""

import pytest

from jarvis.core.app import JarvisApp


@pytest.mark.parametrize("text,spoken", [
    ("abra o navegador", "J.A.R.V.I.S., abra o navegador."),
    ("abra a calculadora", "jarvis abra a calculadora"),
    ("que horas são?", "J.A.R.V.I.S., que horas são?"),
    ("minimize a janela", "jarvis, minimize a janela"),
])
def test_text_and_voice_same_intent(app, text, spoken):
    r_text = app.handle_text(text)
    trace = app.handle_voice_transcript(spoken)
    assert trace.engine_result is not None
    assert r_text.intent == trace.engine_result.intent != "UNKNOWN"


def test_custom_survives_engine_use(app):
    app.custom_commands.create(name="Meu Site", phrases=["abra meu site"],
                               action="open_url",
                               params={"url": "https://example.com"})
    assert app.handle_text("abra meu site").success is True
    trace = app.handle_voice_transcript("jarvis, abra meu site")
    assert trace.engine_result is not None and trace.engine_result.success


def test_aliases_and_native_still_work(app):
    for text in ["abre o navegador", "pode abrir o navegador",
                 "me diga as horas", "tela cheia"]:
        assert app.handle_text(text).success is True, text


def test_settings_and_memory_persist(data_dir):
    app1 = JarvisApp(data_dir=data_dir, dry_run=True)
    app1.start()
    app1.settings.set("tts.rate", 180)
    app1.memory.set_preference("nome", "Senhor")
    app1.handle_text("que horas são?")
    app1.shutdown()

    app2 = JarvisApp(data_dir=data_dir, dry_run=True)
    app2.start()
    try:
        assert app2.settings.get("tts.rate") == 180
        assert app2.memory.get_preference("nome") == "Senhor"
        assert app2.handle_text("que horas são?").success is True
    finally:
        app2.shutdown()


def test_audit_regression_speaking_may_yield_to_work():
    """Achado da auditoria ciclo 1: overlap assíncrono TTS↔pipeline fazia o
    app tentar SPEAKING→EXECUTING e logar 'Transição inválida'. Falar nunca
    pode bloquear trabalho novo chegando."""
    from jarvis.core.states import StateMachine, SystemState as S
    for target in (S.EXECUTING, S.PROCESSING, S.LISTENING):
        sm = StateMachine(initial=S.SPEAKING)
        assert sm.to(target) is True, f"SPEAKING->{target}"
        assert sm.state == target
