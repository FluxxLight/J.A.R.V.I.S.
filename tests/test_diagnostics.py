"""Diagnóstico: 10 verificações reais, nunca levanta."""

from jarvis import __version__
from jarvis.ui.hub.diagnostics import run_diagnostics


def test_diagnostics_shape(app):
    results = run_diagnostics(app)
    assert len(results) == 10
    names = [name for name, _, _ in results]
    assert names == ["Versão", "Armazenamento", "Configurações", "Comandos",
                     "Command Engine", "Microfone", "Reconhecimento",
                     "TTS", "Fila de fala", "Estado"]
    for name, ok, detail in results:
        assert isinstance(ok, bool), name
        assert isinstance(detail, str) and detail, name


def test_diagnostics_core_checks_pass(app):
    results = {name: ok for name, ok, _ in run_diagnostics(app)}
    assert results["Versão"] is True
    assert any(r[0] == "Versão" and __version__ in r[2] for r in run_diagnostics(app))
    assert results["Armazenamento"] is True
    assert results["Configurações"] is True
    assert results["Comandos"] is True
    assert results["Command Engine"] is True
    assert results["Estado"] is True
