"""Command Intelligence Engine (interpretação local, sem LLM)."""

from jarvis.command_engine.engine import CommandEngine, EngineResult
from jarvis.command_engine.normalizer import normalize
from jarvis.command_engine.confirmations import ConfirmationManager

__all__ = ["CommandEngine", "EngineResult", "normalize", "ConfirmationManager"]
