"""Diagnóstico do sistema — verificações reais, sem Qt (testável)."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from jarvis.core.app import JarvisApp


def run_diagnostics(app: "JarvisApp") -> List[Tuple[str, bool, str]]:
    """Retorna [(nome, ok, detalhe)]. Nunca levanta exceção."""
    results: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        results.append((name, bool(ok), str(detail)[:160]))

    # 1) armazenamento
    try:
        base = app.layout["base"]
        add("Armazenamento", base.exists(), str(base))
    except Exception as exc:
        add("Armazenamento", False, str(exc))

    # 2) configurações
    try:
        lang = app.settings.get("language", "?")
        add("Configurações", lang == "pt-BR", f"idioma={lang}")
    except Exception as exc:
        add("Configurações", False, str(exc))

    # 3) comandos
    try:
        n = app.registry.count()
        add("Comandos", n > 0, f"{n} registrados")
    except Exception as exc:
        add("Comandos", False, str(exc))

    # 4) engine (dry smoke: UNKNOWN deve ao menos responder estrutura íntegra)
    try:
        r = app.engine.process("diagnostico interno xyz", source="text")
        add("Command Engine", r is not None and r.intent in ("UNKNOWN",),
            f"intent={r.intent}")
    except Exception as exc:
        add("Command Engine", False, str(exc))

    # 5) microfone
    try:
        from jarvis.voice.microphone import MicStatus
        ok = app.mic.status in (MicStatus.AVAILABLE, MicStatus.BUSY,
                                MicStatus.UNKNOWN)
        add("Microfone", ok, app.mic.status_detail or app.mic.status.value)
    except Exception as exc:
        add("Microfone", False, str(exc))

    # 6) reconhecedor
    try:
        ready = app.recognizer.is_ready()
        add("Reconhecimento", ready,
            "pronto" if ready else app.recognizer.reason()[:120])
    except Exception as exc:
        add("Reconhecimento", False, str(exc))

    # 7) TTS
    try:
        tts = getattr(app.speech, "_tts", None)
        ready = bool(tts is not None and tts.is_ready())
        name = getattr(tts, "name", "?") if tts else "ausente"
        add("TTS", ready, name)
    except Exception as exc:
        add("TTS", False, str(exc))

    # 8) fila de fala
    try:
        add("Fila de fala", app.speech.pending >= 0,
            f"pendentes={app.speech.pending}")
    except Exception as exc:
        add("Fila de fala", False, str(exc))

    # 9) estado
    try:
        add("Estado", True, str(app.states.state))
    except Exception as exc:
        add("Estado", False, str(exc))

    return results
