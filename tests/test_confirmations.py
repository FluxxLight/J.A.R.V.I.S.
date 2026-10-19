"""Ações perigosas exigem confirmação explícita."""

import pytest


@pytest.mark.parametrize("text,intent", [
    ("reinicie o computador", "RESTART_COMPUTER"),
    ("desligue o computador", "SHUTDOWN_COMPUTER"),
    ("feche o jarvis", "EXIT_JARVIS"),
])
def test_dangerous_requires_confirmation(engine, text, intent):
    r = engine.process(text)
    assert r.intent == intent
    assert r.needs_confirmation is True
    assert r.executed is False
    assert "sim" in r.message.lower() or "certeza" in r.message.lower()


def test_confirm_executes(engine):
    engine.process("desligue o computador")
    r = engine.process("sim")
    assert r.success is True and r.executed is True
    assert r.intent == "SHUTDOWN_COMPUTER"


def test_cancel_aborts(engine):
    engine.process("reinicie o computador")
    r = engine.process("não")
    assert r.success is True and r.executed is False
    assert "cancel" in r.message.lower()


def test_unrelated_answer_keeps_pending(engine):
    engine.process("desligue o computador")
    r = engine.process("que horas são?")
    # ainda aguardando sim/não (não executou nem a hora nem o desligamento)
    assert r.needs_confirmation is True
    assert r.executed is False


def test_lock_needs_no_confirmation(engine):
    r = engine.process("bloqueie o computador")
    assert r.intent == "LOCK_COMPUTER"
    assert r.needs_confirmation is False
    assert r.executed is True
