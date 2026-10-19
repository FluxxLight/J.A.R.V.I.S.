"""Pipeline de voz: transcrição -> wake word -> MESMO Command Engine.

Fluxo (com trilha de debug):
    [VOICE RAW] -> [VOICE NORMALIZED] -> [WAKE WORD] ->
    [COMMAND AFTER WAKE WORD] -> [COMMAND ENGINE INPUT] -> [INTENT] ->
    [PARAMETERS] -> [ACTION] -> [EXECUTION] -> [RESULT]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from jarvis.command_engine.engine import CommandEngine, EngineResult
from jarvis.command_engine.normalizer import normalize
from jarvis.logger import get_logger, log_voice_trace
from jarvis.voice.wakeword import WakeResult, detect

log = get_logger("voice.pipeline")

MAX_TRANSCRIPT_CHARS = 500


@dataclass
class VoiceTrace:
    raw: str = ""
    normalized: str = ""
    wake_detected: bool = False
    wake_word: str = ""
    command_after_wake: str = ""
    engine_input: str = ""
    intent: str = "UNKNOWN"
    parameters: dict[str, Any] = field(default_factory=dict)
    action: str = ""
    execution: str = "skipped"
    result: str = ""
    ignored: bool = False
    ignore_reason: str = ""
    engine_result: Optional[EngineResult] = None


class VoiceInputPipeline:
    """Recebe transcrições locais e as envia ao Command Engine."""

    def __init__(self, engine: CommandEngine,
                 wake_word_required: bool = False,
                 extra_wake_words: Optional[List[str]] = None) -> None:
        self.engine = engine
        self.wake_word_required = wake_word_required
        self.extra_wake_words = extra_wake_words or []

    def configure(self, wake_word_required: bool,
                  extra_wake_words: Optional[List[str]] = None) -> None:
        self.wake_word_required = wake_word_required
        self.extra_wake_words = extra_wake_words or []

    def process_transcript(self, transcript: str | None) -> VoiceTrace:
        """Processa UMA transcrição. Nunca levanta exceção."""
        trace = VoiceTrace()
        try:
            return self._process(transcript, trace)
        except Exception as exc:  # última barreira
            log.exception("Falha no pipeline de voz")
            trace.execution = "error"
            trace.result = f"erro interno: {exc}"
            log_voice_trace(log, trace)
            return trace

    def _process(self, transcript: str | None, trace: VoiceTrace) -> VoiceTrace:
        # [VOICE RAW]
        if transcript is None:
            trace.raw = ""
            trace.ignored = True
            trace.ignore_reason = "transcricao None"
            trace.result = "ignorado: transcrição vazia"
            log_voice_trace(log, trace)
            return trace
        raw = str(transcript).strip()
        if len(raw) > MAX_TRANSCRIPT_CHARS:
            log.warning("Transcrição longa (%d). Truncando.", len(raw))
            raw = raw[:MAX_TRANSCRIPT_CHARS]
        trace.raw = raw

        # [VOICE NORMALIZED]
        trace.normalized = normalize(raw)
        if not raw or not trace.normalized:
            trace.ignored = True
            trace.ignore_reason = "texto vazio"
            trace.result = "ignorado: texto vazio"
            log_voice_trace(log, trace)
            return trace

        # [WAKE WORD] + [COMMAND AFTER WAKE WORD]
        wake: WakeResult = detect(raw, self.extra_wake_words)
        trace.wake_detected = wake.detected
        trace.wake_word = wake.wake_word
        trace.command_after_wake = wake.command_text

        if wake.detected and not wake.command_text.strip():
            # "Jarvis." sozinho -> confirma presença, não executa nada
            trace.ignored = True
            trace.ignore_reason = "somente wake word"
            trace.execution = "ack"
            trace.result = "ack: somente wake word"
            trace.engine_result = EngineResult(
                success=True, intent="WAKE_ACK", normalized=trace.normalized,
                message="Pois não?", speak_text="Pois não?")
            log_voice_trace(log, trace)
            return trace

        if self.wake_word_required and not wake.detected:
            trace.ignored = True
            trace.ignore_reason = "wake word obrigatória ausente"
            trace.result = "ignorado: sem wake word"
            log_voice_trace(log, trace)
            return trace

        # [COMMAND ENGINE INPUT] — o MESMO engine do texto
        trace.engine_input = wake.command_text if wake.detected else raw
        log.info("VOICE -> ENGINE: %r (wake=%s)", trace.engine_input, wake.detected)

        result = self.engine.process(trace.engine_input, source="voice")
        trace.engine_result = result
        trace.intent = result.intent
        trace.parameters = result.params
        trace.action = result.action_id
        trace.execution = ("executed" if result.executed else
                           "confirmation" if result.needs_confirmation else
                           "rejected")
        trace.result = result.message
        log_voice_trace(log, trace)
        return trace
