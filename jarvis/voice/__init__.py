"""Voz local: wake word, pipeline, microfone, reconhecimento e TTS."""

from jarvis.voice.pipeline import VoiceInputPipeline, VoiceTrace
from jarvis.voice.wakeword import WakeResult, detect
from jarvis.voice.queue import SpeechQueue

__all__ = ["VoiceInputPipeline", "VoiceTrace", "WakeResult", "detect", "SpeechQueue"]
