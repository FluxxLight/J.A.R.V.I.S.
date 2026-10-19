"""Pipeline de voz com transcrições simuladas (lógica 100% testável).

Casos obrigatórios do Prompt 1.2:
- texto e voz chegam à MESMA intenção;
- comando após a wake word é preservado.
"""

import pytest


@pytest.mark.parametrize("spoken,intent", [
    ("abra o navegador", "OPEN_BROWSER"),
    ("J.A.R.V.I.S., abra o navegador.", "OPEN_BROWSER"),
    ("jarvis abra o navegador", "OPEN_BROWSER"),
    ("abra a calculadora", "OPEN_CALCULATOR"),
    ("J.A.R.V.I.S., abra a calculadora", "OPEN_CALCULATOR"),
    ("que horas são?", "GET_TIME"),
    ("J.A.R.V.I.S., que horas são?", "GET_TIME"),
    ("abre a calculadora", "OPEN_CALCULATOR"),
])
def test_voice_reaches_same_intent(voice, spoken, intent):
    trace = voice.process_transcript(spoken)
    assert trace.ignored is False, trace
    assert trace.intent == intent, trace
    assert trace.engine_result is not None and trace.engine_result.success


def test_command_after_wake_preserved(voice):
    trace = voice.process_transcript("J.A.R.V.I.S., abra o navegador.")
    assert trace.wake_detected is True
    assert trace.command_after_wake == "abra o navegador."
    assert trace.engine_input == "abra o navegador."
    assert trace.intent == "OPEN_BROWSER"


def test_unknown_voice_command(voice):
    trace = voice.process_transcript("comando inexistente blablabla")
    assert trace.ignored is False
    assert trace.intent == "UNKNOWN"


def test_wake_only_ack(voice):
    for only in ["J.A.R.V.I.S.", "J.A.R.V.I.S.,", "jarvis"]:
        trace = voice.process_transcript(only)
        assert trace.wake_detected is True
        assert trace.engine_result is not None
        assert trace.engine_result.success is True
        assert "pois n" in trace.engine_result.message.lower()


def test_wake_required_mode(engine):
    from jarvis.voice.pipeline import VoiceInputPipeline
    strict = VoiceInputPipeline(engine, wake_word_required=True)
    ignored = strict.process_transcript("abra o navegador")
    assert ignored.ignored is True
    assert "wake" in ignored.ignore_reason.lower()
    ok = strict.process_transcript("jarvis, abra o navegador")
    assert ok.ignored is False and ok.intent == "OPEN_BROWSER"


def test_trace_has_full_debug_fields(voice):
    trace = voice.process_transcript("jarvis, que horas são?")
    for field in ("raw", "normalized", "wake_detected", "command_after_wake",
                  "engine_input", "intent", "parameters", "action",
                  "execution", "result"):
        assert hasattr(trace, field), field
    assert trace.action == "GetTime"
    assert trace.execution == "executed"
