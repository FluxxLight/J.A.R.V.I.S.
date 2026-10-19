"""Contexto: pronomes, continuação e repetição por regras."""

from jarvis.context.context import ContextManager, Interaction


def _push(ctx, text, normalized, intent, app=None):
    ctx.push(Interaction(text=text, normalized=normalized, intent=intent, app=app))


def test_pronoun_resolves_to_last_app():
    ctx = ContextManager()
    _push(ctx, "abra o discord", "abra o discord", "OPEN_APP", app="discord")
    res = ctx.resolve("feche ele")
    assert res.applied is True
    assert "discord" in (res.rewritten_text or "")


def test_pronoun_without_context():
    ctx = ContextManager()
    res = ctx.resolve("feche ele")
    assert res.applied is False


def test_continuation_after_open():
    ctx = ContextManager()
    _push(ctx, "abra o navegador", "abra o navegador", "OPEN_BROWSER", app="browser")
    res = ctx.resolve("agora o youtube")
    assert res.applied is True
    assert (res.rewritten_text or "").startswith("abrir")


def test_repeat_last_safe():
    ctx = ContextManager()
    _push(ctx, "que horas sao", "que horas sao", "GET_TIME")
    res = ctx.resolve("de novo")
    assert res.applied is True
    assert res.rewritten_text == "que horas sao"


def test_repeat_dangerous_refused():
    ctx = ContextManager()
    _push(ctx, "desligue o computador", "desligue o computador", "SHUTDOWN_COMPUTER")
    res = ctx.resolve("de novo")
    assert res.applied is False


def test_engine_uses_context_for_pronoun(engine):
    engine.process("abra o discord")
    # "feche ele" não é comando nativo de fechar app; o teste garante que o
    # contexto ao menos reescreveu (intent pode ser UNKNOWN, mas aplicado).
    res = engine.context.resolve("feche ele")
    assert res.applied is True
