"""Gerenciador de microfone (inicialização, captura, erros, liberação).

Sem dependências obrigatórias: usa `sounddevice` se instalado; caso
contrário opera em modo indisponível com mensagem clara (sem crash).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional

from jarvis.logger import get_logger

log = get_logger("voice.mic")


class MicStatus(str, Enum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BUSY = "busy"
    ERROR = "error"


@dataclass
class MicDevice:
    index: int
    name: str
    channels_in: int = 0
    sample_rate: float = 0.0

    def __str__(self) -> str:
        return f"[{self.index}] {self.name}"


def _import_sounddevice():
    try:
        import sounddevice  # type: ignore[import-not-found]
        return sounddevice
    except ImportError:
        return None


class MicrophoneManager:
    def __init__(self, device_index: Optional[int] = None,
                 sample_rate: int = 16000) -> None:
        self._lock = threading.RLock()
        self._device_index = device_index
        self._sample_rate = sample_rate
        self._status = MicStatus.UNKNOWN
        self._status_detail = ""
        self._stream: Any = None

    @property
    def status(self) -> MicStatus:
        with self._lock:
            return self._status

    @property
    def status_detail(self) -> str:
        with self._lock:
            return self._status_detail

    def _set(self, status: MicStatus, detail: str = "") -> None:
        with self._lock:
            self._status = status
            self._status_detail = detail
        log.info("Microfone: %s %s", status.value, detail)

    # -- dispositivos ------------------------------------------------------
    def list_devices(self) -> List[MicDevice]:
        sd = _import_sounddevice()
        if sd is None:
            self._set(MicStatus.UNAVAILABLE,
                      "Biblioteca 'sounddevice' não instalada (pip install sounddevice).")
            return []
        try:
            devices = sd.query_devices()
            result = []
            for i, dev in enumerate(devices):
                if int(dev.get("max_input_channels", 0)) > 0:
                    result.append(MicDevice(
                        index=i, name=str(dev.get("name", f"device {i}")),
                        channels_in=int(dev["max_input_channels"]),
                        sample_rate=float(dev.get("default_samplerate", 0) or 0)))
            if result:
                self._set(MicStatus.AVAILABLE, f"{len(result)} dispositivo(s).")
            else:
                self._set(MicStatus.UNAVAILABLE, "Nenhum microfone detectado.")
            return result
        except Exception as exc:
            self._set(MicStatus.ERROR, f"Falha ao listar dispositivos: {exc}")
            log.exception("list_devices falhou")
            return []

    def check_available(self) -> bool:
        devices = self.list_devices()
        if self._device_index is not None:
            ok = any(d.index == self._device_index for d in devices)
            if not ok:
                self._set(MicStatus.UNAVAILABLE,
                          f"Dispositivo {self._device_index} não encontrado.")
            return ok
        return len(devices) > 0

    def set_device(self, index: Optional[int]) -> None:
        with self._lock:
            self._device_index = index
        log.info("Dispositivo de captura: %s", index)

    # -- stream ------------------------------------------------------------
    def open_stream(self, block_size: int = 1600):
        """Abre stream de captura. Retorna objeto com .read()/.close() ou None.

        block_size padrão 1600 amostras @ 16 kHz = 100 ms (bom para VAD).
        """
        sd = _import_sounddevice()
        if sd is None:
            self._set(MicStatus.UNAVAILABLE, "sounddevice ausente.")
            return None
        with self._lock:
            if self._stream is not None:
                return self._stream
            try:
                stream = sd.RawInputStream(
                    samplerate=self._sample_rate, blocksize=block_size,
                    device=self._device_index, channels=1, dtype="int16")
                stream.start()
                self._stream = stream
                self._set(MicStatus.BUSY, "capturando")
                log.info("Stream de microfone aberto (device=%s, %d Hz).",
                         self._device_index, self._sample_rate)
                return stream
            except Exception as exc:
                self._set(MicStatus.ERROR, f"Falha ao abrir microfone: {exc}")
                log.exception("open_stream falhou")
                return None

    def close_stream(self) -> None:
        with self._lock:
            stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                log.exception("Erro ao fechar stream (não fatal)")
            finally:
                self._set(MicStatus.AVAILABLE, "stream fechado")

    def release(self) -> None:
        self.close_stream()
