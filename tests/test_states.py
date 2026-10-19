"""Estados: fluxo feliz, erro/recuperação e transições inválidas."""

from jarvis.core.states import StateMachine, SystemState as S


def test_happy_flow():
    sm = StateMachine()
    assert sm.to(S.STARTING)
    assert sm.to(S.READY)
    assert sm.to(S.IDLE)
    assert sm.to(S.LISTENING)
    assert sm.to(S.PROCESSING)
    assert sm.to(S.EXECUTING)
    assert sm.to(S.SPEAKING)
    assert sm.to(S.READY)
    assert sm.state == S.READY


def test_error_and_recover():
    sm = StateMachine()
    sm.to(S.STARTING, force=True)
    sm.to(S.PROCESSING)
    sm.fail("teste")
    assert sm.state == S.ERROR
    sm.recover()
    assert sm.state == S.READY


def test_invalid_transition_rejected():
    sm = StateMachine()
    sm.to(S.STARTING, force=True)
    assert sm.to(S.EXECUTING) is False  # pula etapas: inválido
    assert sm.state == S.STARTING


def test_listeners_called():
    sm = StateMachine()
    seen = []
    sm.add_listener(lambda o, n: seen.append((o, n)))
    sm.to(S.STARTING)
    sm.to(S.READY)
    assert (S.STARTING, S.READY) in seen


def test_no_stuck_states_via_app(app):
    import time
    app.handle_text("que horas são?")
    assert app.speech.wait_until_done(timeout=10)
    deadline = time.time() + 5
    while app.states.state != S.IDLE and time.time() < deadline:
        time.sleep(0.05)
    assert app.states.state == S.IDLE
    app.handle_voice_transcript("jarvis, que horas são?")
    assert app.speech.wait_until_done(timeout=10)
    deadline = time.time() + 5
    while app.states.state != S.IDLE and time.time() < deadline:
        time.sleep(0.05)
    assert app.states.state == S.IDLE
