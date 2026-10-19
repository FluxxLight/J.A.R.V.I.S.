"""JarvisApp — orquestrador: liga Core+Engine+Voz+Storage+UI.

Ciclo de vida:
    app = JarvisApp()
    app.start()            # STARTING -> READY
    app.handle_text(...)   # IDLE->PROCESSING->EXECUTING->SPEAKING->READY
    app.listen_once(...)   # LISTENING->PROCESSING->... (voz real)
    app.shutdown()         # libera microfone, TTS, threads, arquivos
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, List, Optional

from jarvis.actions.system import register_all as register_actions
from jarvis.command_engine.engine import CommandEngine, EngineResult
from jarvis.commands.custom import CustomCommandManager
from jarvis.commands.native import register_all as register_native
from jarvis.commands.registry import CommandRegistry
from jarvis.context.context import ContextManager
from jarvis.core.events import (APP_SHUTDOWN, COMMAND_EXECUTED, COMMAND_RECEIVED,
                                SPEECH_FINISHED, SPEECH_STARTED, STATE_CHANGED,
                                VOICE_TRANSCRIPT, EventBus)
from jarvis.core.pipeline import process_command
from jarvis.core.states import StateMachine, SystemState
from jarvis.logger import get_logger, setup_logging
from jarvis.memory.memory import MemoryManager
from jarvis.settings.settings import SettingsManager
from jarvis.storage import paths
from jarvis.voice.microphone import MicDevice, MicrophoneManager
from jarvis.voice.pipeline import VoiceInputPipeline, VoiceTrace
from jarvis.voice.queue import SpeechQueue
from jarvis.voice.recognizer import LocalRecognizer, create_recognizer
from jarvis.voice.tts import LocalTTS, VoiceInfo, create_tts

log = get_logger("core.app")


class JarvisApp:
    def __init__(self, data_dir: Optional[Path | str] = None,
                 dry_run: bool = False) -> None:
        if data_dir:
            paths.set_base_dir(data_dir)
        self.layout = paths.ensure_layout()
        setup_logging(self.layout["logs"])
        log.info("=== J.A.R.V.I.S. iniciando ===")

        self.events = EventBus()
        self.states = StateMachine()
        self.states.add_listener(self._on_state_changed)

        self.settings = SettingsManager()
        self.memory = MemoryManager()
        self.context = ContextManager()
        self.registry = CommandRegistry()

        register_actions(self.registry)
        register_native(self.registry)
        self.custom_commands = CustomCommandManager(self.registry)

        self.engine = CommandEngine(
            registry=self.registry, context=self.context, memory=self.memory,
            confirm_dangerous=bool(
                self.settings.get("behavior.confirm_dangerous", True)),
            request_exit=self.request_exit, dry_run=dry_run)
        self.dry_run = dry_run

        # voz
        self.voice_pipeline = VoiceInputPipeline(
            self.engine,
            wake_word_required=bool(
                self.settings.get("voice.wake_word_required", False)))
        self.mic = MicrophoneManager(
            device_index=self.settings.get("voice.device_index"),
            sample_rate=int(self.settings.get("voice.sample_rate", 16000)))
        self.recognizer: LocalRecognizer = create_recognizer(
            model_path=str(self.settings.get("voice.model_path", "") or ""),
            sample_rate=int(self.settings.get("voice.sample_rate", 16000)))
        tts_backend: LocalTTS = create_tts(
            enabled=bool(self.settings.get("tts.enabled", True)),
            voice_id=str(self.settings.get("tts.voice_id", "") or ""),
            rate=int(self.settings.get("tts.rate", 170)),
            volume=float(self.settings.get("tts.volume", 0.9)))
        self.speech = SpeechQueue(tts_backend, on_start=self._on_speech_start,
                                  on_finish=self._on_speech_finish)

        self._exit_event = threading.Event()
        self._lock = threading.RLock()
        self._started = False

    # -- ciclo de vida ------------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self.states.to(SystemState.STARTING, force=True)
            log.info("Comandos: %d | Reconhecedor: %s (%s) | dry_run=%s",
                     self.registry.count(), self.recognizer.name,
                     "pronto" if self.recognizer.is_ready() else self.recognizer.reason(),
                     self.dry_run)
            self.states.to(SystemState.READY)
            self.states.to(SystemState.IDLE)
            self._started = True
            log.info("J.A.R.V.I.S. pronto.")

    def request_exit(self) -> None:
        log.info("Saída solicitada.")
        self._exit_event.set()

    @property
    def exit_requested(self) -> bool:
        return self._exit_event.is_set()

    def shutdown(self) -> None:
        with self._lock:
            log.info("Encerrando J.A.R.V.I.S. ...")
            try:
                self.states.to(SystemState.SHUTDOWN, force=True)
            except Exception:
                pass
            try:
                self.events.emit(APP_SHUTDOWN)
            except Exception:
                pass
            # libera recursos: fala -> reconhecedor -> microfone
            try:
                self.speech.shutdown(wait=True)
            except Exception:
                log.exception("speech.shutdown falhou")
            try:
                self.recognizer.close()
            except Exception:
                log.exception("recognizer.close falhou")
            try:
                self.mic.release()
            except Exception:
                log.exception("mic.release falhou")
            log.info("=== J.A.R.V.I.S. encerrado ===")

    # -- entradas -----------------------------------------------------------
    def handle_text(self, text: str) -> EngineResult:
        """Entrada DIGITADA (UI/CLI). Usa o Command Engine."""
        self.states.to(SystemState.PROCESSING)
        self.events.emit(COMMAND_RECEIVED, text=text, source="text")
        try:
            self.states.to(SystemState.EXECUTING)
            result = process_command(self.engine, text, source="text")
            self.events.emit(COMMAND_EXECUTED, result=result)
            self._speak_result(result)
            self.states.to(SystemState.READY)
            self.states.to(SystemState.IDLE)
            return result
        except Exception as exc:
            log.exception("handle_text falhou")
            self.states.fail(str(exc))
            self.states.recover()
            return EngineResult(success=False, message=f"Erro: {exc}",
                                speak_text="Ocorreu um erro.")

    def handle_voice_transcript(self, transcript: str | None) -> VoiceTrace:
        """Entrada de VOZ já transcrita. Usa o MESMO Command Engine."""
        self.states.to(SystemState.PROCESSING)
        self.events.emit(VOICE_TRANSCRIPT, transcript=transcript)
        try:
            trace = self.voice_pipeline.process_transcript(transcript)
            if trace.engine_result is not None:
                self.events.emit(COMMAND_EXECUTED, result=trace.engine_result)
                self._speak_result(trace.engine_result)
            self.states.to(SystemState.READY)
            self.states.to(SystemState.IDLE)
            return trace
        except Exception as exc:
            log.exception("handle_voice_transcript falhou")
            self.states.fail(str(exc))
            self.states.recover()
            trace = VoiceTrace(raw=str(transcript or ""), result=f"Erro: {exc}")
            return trace

    def listen_once(self, timeout: Optional[float] = None) -> VoiceTrace:
        """Captura UMA fala do microfone e processa (voz real, local)."""
        if not bool(self.settings.get("voice.enabled", True)):
            trace = VoiceTrace(ignored=True, ignore_reason="voz desativada",
                               result="Reconhecimento de voz desativado.")
            return trace
        if not self.recognizer.is_ready():
            reason = self.recognizer.reason()
            log.warning("listen_once indisponível: %s", reason)
            self.speak("Reconhecimento de voz indisponível. " + reason)
            return VoiceTrace(ignored=True, ignore_reason=reason, result=reason)
        self.states.to(SystemState.LISTENING)
        seconds = float(timeout if timeout is not None
                        else self.settings.get("voice.listen_timeout", 8))
        try:
            transcript = self.recognizer.listen_once(self.mic, timeout=seconds)
        except Exception as exc:
            log.exception("Captura falhou")
            self.states.fail(str(exc))
            self.states.recover()
            return VoiceTrace(ignored=True, ignore_reason=str(exc),
                              result=f"Falha na captura: {exc}")
        if not transcript.text.strip():
            log.info("Nada capturado (silêncio).")
            self.states.to(SystemState.IDLE)
            return VoiceTrace(raw="", ignored=True, ignore_reason="silêncio",
                              result="Não ouvi nada.")
        return self.handle_voice_transcript(transcript.text)

    # -- fala ----------------------------------------------------------------
    def speak(self, text: str, interrupt: bool = False) -> None:
        if not bool(self.settings.get("tts.enabled", True)):
            log.info("[fala suprimida, tts off] %s", text)
            return
        self.speech.speak(text, interrupt=interrupt)

    def _speak_result(self, result: EngineResult) -> None:
        if result.speak_text:
            self.speak(result.speak_text)

    def _on_speech_start(self, text: str) -> None:
        self.states.to(SystemState.SPEAKING)
        self.events.emit(SPEECH_STARTED, text=text)

    def _on_speech_finish(self, text: str) -> None:
        self.events.emit(SPEECH_FINISHED, text=text)
        if self.states.state == SystemState.SPEAKING:
            self.states.to(SystemState.READY)
            self.states.to(SystemState.IDLE)

    # -- diagnósticos ---------------------------------------------------------
    def list_microphones(self) -> List[MicDevice]:
        return self.mic.list_devices()

    def list_voices(self) -> List[VoiceInfo]:
        tts = getattr(self.speech, "_tts", None)
        try:
            return tts.list_voices() if tts else []
        except Exception:
            return []

    def recognizer_status(self) -> str:
        if self.recognizer.is_ready():
            return f"pronto ({self.recognizer.name})"
        return f"indisponível: {self.recognizer.reason()}"

    def _on_state_changed(self, old: SystemState, new: SystemState) -> None:
        try:
            self.events.emit(STATE_CHANGED, old=old, new=new)
        except Exception:
            pass
