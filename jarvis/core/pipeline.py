"""Pipeline unificado: TEXTO e VOZ convergem para `process_command`.

    process_command(text, source="text"|"voice") -> EngineResult

A voz NUNCA interpreta por conta própria: ela transcreve (local),
trata a wake word e chama esta mesma função.
"""

from __future__ import annotations

from jarvis.command_engine.engine import CommandEngine, EngineResult
from jarvis.logger import get_logger

log = get_logger("core.pipeline")


def process_command(engine: CommandEngine, text: str | None,
                    source: str = "text") -> EngineResult:
    """Ponto único de interpretação+execução. Nunca levanta exceção."""
    try:
        return engine.process(text, source=source)
    except Exception as exc:  # paranoia: engine já trata, mas garantimos
        log.exception("process_command falhou")
        return EngineResult(success=False,
                            message=f"Erro interno: {exc}",
                            speak_text="Desculpe, ocorreu um erro interno.")
