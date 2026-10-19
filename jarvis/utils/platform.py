"""Detecção de plataforma (alvo principal: Windows)."""

from __future__ import annotations

import platform
import sys


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    return sys.platform == "darwin"


def system_name() -> str:
    return platform.system()


def describe() -> str:
    return f"{platform.system()} {platform.release()} ({platform.machine()})"
