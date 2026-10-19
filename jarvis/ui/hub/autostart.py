"""'Inicializar com o Windows' — implementação real via Registro.

- Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\JARVIS
  (por usuário, sem admin, reversível, sem duplicação).
- Outras plataformas: indisponível (motivo claro, sem crash).

Backend injetável -> testável sem Windows e sem Registro real.
"""

from __future__ import annotations

from typing import Optional

from jarvis.logger import get_logger
from jarvis.utils.platform import is_windows

log = get_logger("ui.autostart")

APP_KEY = "JARVIS"
RUN_SUBKEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class AutostartBackend:
    def is_available(self) -> tuple[bool, str]:
        raise NotImplementedError

    def is_enabled(self, command: str = "") -> bool:
        raise NotImplementedError

    def set_enabled(self, enabled: bool, command: str) -> tuple[bool, str]:
        raise NotImplementedError


class WindowsRegistryBackend(AutostartBackend):
    def is_available(self) -> tuple[bool, str]:
        if not is_windows():
            return False, "Inicialização automática disponível apenas no Windows."
        try:
            import winreg  # type: ignore[import-not-found]
        except ImportError:
            return False, "winreg indisponível."
        return True, ""

    def is_enabled(self, command: str = "") -> bool:
        if not is_windows():
            return False
        try:
            import winreg
        except ImportError:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_SUBKEY) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, APP_KEY)
                except FileNotFoundError:
                    return False
            if command and value != command:
                return False  # entrada existe mas aponta para outro lugar
            return True
        except OSError as exc:
            log.warning("Falha ao ler autostart: %s", exc)
            return False

    def set_enabled(self, enabled: bool, command: str) -> tuple[bool, str]:
        ok, reason = self.is_available()
        if not ok:
            return False, reason
        if enabled and not command.strip():
            return False, "Comando de inicialização vazio."
        try:
            import winreg
        except ImportError:
            return False, "winreg indisponível."
        try:
            if enabled:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_SUBKEY,
                                    0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, APP_KEY, 0, winreg.REG_SZ, command)
                log.info("Autostart ATIVADO: %s", command)
                return True, "J.A.R.V.I.S. iniciará com o Windows."
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_SUBKEY,
                                0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, APP_KEY)
                except FileNotFoundError:
                    pass
            log.info("Autostart DESATIVADO.")
            return True, "Inicialização automática desativada."
        except OSError as exc:
            log.exception("Falha ao gravar autostart")
            return False, f"Falha ao alterar inicialização: {exc}"


class MemoryBackend(AutostartBackend):
    """Backend falso para testes (simula o Registro em memória)."""

    def __init__(self, available: bool = True) -> None:
        self._available = available
        self._value: Optional[str] = None

    def is_available(self) -> tuple[bool, str]:
        return (self._available,
                "" if self._available else "Backend de teste indisponível.")

    def is_enabled(self, command: str = "") -> bool:
        if self._value is None:
            return False
        if command and self._value != command:
            return False
        return True

    def set_enabled(self, enabled: bool, command: str) -> tuple[bool, str]:
        if not self._available:
            return False, "Backend de teste indisponível."
        if enabled:
            if not command.strip():
                return False, "Comando vazio."
            self._value = command
            return True, "ok"
        self._value = None
        return True, "ok"


class AutostartManager:
    def __init__(self, backend: Optional[AutostartBackend] = None) -> None:
        self._backend = backend or WindowsRegistryBackend()

    def is_available(self) -> tuple[bool, str]:
        return self._backend.is_available()

    def is_enabled(self, command: str = "") -> bool:
        return self._backend.is_enabled(command)

    def set_enabled(self, enabled: bool, command: str) -> tuple[bool, str]:
        return self._backend.set_enabled(enabled, command)


def default_start_command() -> str:
    """Comando registrado no Run: EXE empacotado ou `python main.py --hub`."""
    import sys
    from pathlib import Path
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable or "python"
    # jarvis/ui/hub/autostart.py -> raiz do projeto
    root = Path(__file__).resolve().parents[3]
    candidate = root / "main.py"
    return f'"{exe}" "{candidate}" --hub'
