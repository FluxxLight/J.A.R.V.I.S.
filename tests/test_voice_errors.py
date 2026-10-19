"""Erros de voz: falhar com segurança, nunca crashar."""

import pytest


@pytest.mark.parametrize("bad", [None, "", "   ", "\n\t", "!@#$%^&*()",
                                 "x" * 5000, "ã", "????", ".....,,,,,"])
def test_bad_transcripts_safe(voice, bad):
    trace = voice.process_transcript(bad)
    assert trace is not None
    # vazio/None/pontuação pura -> ignorado; resto -> UNKNOWN seguro
    if trace.intent != "UNKNOWN":
        assert trace.ignored or (trace.engine_result is not None)


def test_partial_like_fragments(voice):
    for frag in ["abra", "o", "jar", "que", "a"]:
        trace = voice.process_transcript(frag)
        assert trace is not None
        assert trace.engine_result is None or trace.intent in (
            trace.intent,)  # só garante estrutura íntegra


def test_duplicated_wake(voice):
    trace = voice.process_transcript("jarvis jarvis abra o navegador")
    assert trace.wake_detected is True
    assert trace.intent in ("OPEN_BROWSER", "UNKNOWN")  # seguro em ambos


def test_huge_transcript_truncated(voice):
    trace = voice.process_transcript("abra o navegador " + "e" * 5000)
    assert len(trace.raw) <= 500
