"""Logging profissional local do J.A.R.V.I.S. (somente stdlib).

- Arquivo rotativo em <data>/logs/jarvis.log
- Console com nível configurável
- Logger nomeado por módulo: jarvis.<modulo>
- Helper de trilha de voz (VOICE RAW -> RESULT) para depuração
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_configured = False
_log_file: Optional[Path] = None

FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: Path | str, console_level: int = logging.INFO,
                  file_level: int = logging.DEBUG) -> Path:
    """Configura o logging global. Idempotente. Retorna o caminho do log."""
    global _configured, _log_file
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "jarvis.log"

    if _configured and _log_file == log_file:
        return log_file

    root = logging.getLogger("jarvis")
    root.setLevel(logging.DEBUG)
    for old_handler in list(root.handlers):
        try:
            root.removeHandler(old_handler)
            old_handler.close()
        except Exception:
            pass
    root.propagate = False

    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))

    root.addHandler(file_handler)
    root.addHandler(console)

    _configured = True
    _log_file = log_file
    root.info("Logging inicializado em %s", log_file)
    return log_file


def get_logger(name: str) -> logging.Logger:
    """Retorna logger do módulo. Garante ao menos um handler de console."""
    logger = logging.getLogger(name if name.startswith("jarvis") else f"jarvis.{name}")
    if not logging.getLogger("jarvis").handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))
        logging.getLogger("jarvis").addHandler(handler)
        logging.getLogger("jarvis").setLevel(logging.DEBUG)
    return logger


def log_voice_trace(logger: logging.Logger, trace: object) -> None:
    """Registra a trilha completa voz -> comando (depuração da integração)."""
    lines = ["[VOICE TRACE]"]
    mapping = (
        ("raw", "RAW TRANSCRIPT"),
        ("normalized", "NORMALIZED"),
        ("wake_detected", "WAKE WORD"),
        ("command_after_wake", "COMMAND"),
        ("engine_input", "ENGINE INPUT"),
        ("intent", "INTENT"),
        ("parameters", "PARAMETERS"),
        ("action", "EXECUTION"),
        ("execution", "STATUS"),
        ("result", "RESULT"),
    )
    for field, label in mapping:
        value = getattr(trace, field, "?")
        lines.append(f"  [{label}] {value!r}")
    logger.info("\n".join(lines))
