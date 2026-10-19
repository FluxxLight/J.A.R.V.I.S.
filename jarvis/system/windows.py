"""Operações de baixo nível no Windows (ctypes, sem dependências).

Em outras plataformas, cada função retorna (False, motivo) em vez de falhar.
"""

from __future__ import annotations

import ctypes
from typing import Optional, Tuple

from jarvis.logger import get_logger
from jarvis.utils.platform import is_windows

log = get_logger("system.windows")


def _user32():
    return ctypes.windll.user32  # type: ignore[attr-defined]


def lock_workstation() -> Tuple[bool, str]:
    if not is_windows():
        return False, "Bloqueio disponível apenas no Windows."
    try:
        ok = _user32().LockWorkStation()
        return (True, "Computador bloqueado.") if ok else (False, "Falha ao bloquear.")
    except Exception as exc:
        log.exception("LockWorkStation falhou")
        return False, f"Erro ao bloquear: {exc}"


def _shutdown_windows(action: str) -> Tuple[bool, str]:
    """action: 'shutdown' | 'restart'. Usa shutdown.exe com aviso de 10s."""
    import subprocess

    if not is_windows():
        return False, "Disponível apenas no Windows."
    flag = "/s" if action == "shutdown" else "/r"
    try:
        subprocess.Popen(
            ["shutdown", flag, "/t", "10", "/c", "J.A.R.V.I.S.: ação solicitada."],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        what = "desligamento" if action == "shutdown" else "reinício"
        return True, f"{what.capitalize()} agendado em 10 segundos."
    except Exception as exc:
        log.exception("shutdown.exe falhou")
        return False, f"Erro: {exc}"


def shutdown_computer() -> Tuple[bool, str]:
    return _shutdown_windows("shutdown")


def restart_computer() -> Tuple[bool, str]:
    return _shutdown_windows("restart")


def abort_shutdown() -> Tuple[bool, str]:
    import subprocess

    if not is_windows():
        return False, "Disponível apenas no Windows."
    try:
        subprocess.run(["shutdown", "/a"], capture_output=True, timeout=10)
        return True, "Agendamento cancelado."
    except Exception as exc:
        return False, f"Erro: {exc}"


def _foreground_window():
    try:
        return _user32().GetForegroundWindow()
    except Exception:
        return None


def minimize_foreground() -> Tuple[bool, str]:
    if not is_windows():
        return False, "Disponível apenas no Windows."
    try:
        hwnd = _foreground_window()
        if not hwnd:
            return False, "Nenhuma janela ativa."
        _user32().ShowWindow(hwnd, 6)  # SW_MINIMIZE
        return True, "Janela minimizada."
    except Exception as exc:
        log.exception("Minimizar falhou")
        return False, f"Erro: {exc}"


def maximize_foreground() -> Tuple[bool, str]:
    if not is_windows():
        return False, "Disponível apenas no Windows."
    try:
        hwnd = _foreground_window()
        if not hwnd:
            return False, "Nenhuma janela ativa."
        _user32().ShowWindow(hwnd, 3)  # SW_MAXIMIZE
        return True, "Janela maximizada."
    except Exception as exc:
        log.exception("Maximizar falhou")
        return False, f"Erro: {exc}"


def toggle_fullscreen_foreground() -> Tuple[bool, str]:
    """Alterna maximizada <-> restaurada (fullscreen prático no Windows)."""
    if not is_windows():
        return False, "Disponível apenas no Windows."
    try:
        hwnd = _foreground_window()
        if not hwnd:
            return False, "Nenhuma janela ativa."
        # IsZoomed -> restaurada (9), senão maximizada (3)
        if _user32().IsZoomed(hwnd):
            _user32().ShowWindow(hwnd, 9)  # SW_RESTORE
            return True, "Janela restaurada."
        _user32().ShowWindow(hwnd, 3)
        return True, "Janela em tela cheia."
    except Exception as exc:
        log.exception("Fullscreen falhou")
        return False, f"Erro: {exc}"


def close_app_windows(exe_names: list[str], title_hint: str = "") -> Tuple[bool, str]:
    """Fecha janelas visíveis de um app (por executável ou título). Suave: WM_CLOSE.

    Retorna (True, msg) se ao menos uma janela foi sinalizada.
    """
    import ctypes

    if not is_windows():
        return False, "Fechar aplicativos disponível apenas no Windows."
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
    except Exception as exc:
        return False, f"API do Windows indisponível: {exc}"

    targets = {n.strip().lower() for n in (exe_names or []) if n and n.strip()}
    hint = (title_hint or "").strip().lower()
    closed = 0

    def _process_exe(pid: int) -> str:
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
        if not handle:
            return ""
        try:
            size = ctypes.c_uint(260)
            buf = ctypes.create_unicode_buffer(260)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return str(buf.value).rsplit("\\", 1)[-1].lower()
            return ""
        except Exception:
            return ""
        finally:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass

    def _callback(hwnd, _param) -> bool:
        nonlocal closed
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = int(user32.GetWindowTextLengthW(hwnd) or 0)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = str(buf.value or "")
            pid = ctypes.c_uint(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            exe = _process_exe(pid.value) if pid.value else ""
            match = bool(exe and exe in targets)
            if not match and hint and len(hint) >= 3 and hint in title.lower():
                match = True
            if match:
                user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                closed += 1
        except Exception:
            log.exception("close_app_windows: janela ignorada (não fatal)")
        return True

    try:
        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(CMPFUNC(_callback), 0)
    except Exception as exc:
        log.exception("EnumWindows falhou")
        return False, f"Falha ao fechar: {exc}"
    if closed > 0:
        plural = "s" if closed > 1 else ""
        return True, f"Fechada{plural} {closed} janela{plural}."
    return False, "Nenhuma janela encontrada para esse aplicativo."


def open_windows_settings(section: str = "") -> Tuple[bool, str]:
    """Abre Configurações do Windows (ms-settings:)."""
    import subprocess

    if not is_windows():
        return False, "Configurações do Windows indisponíveis aqui."
    target = f"ms-settings:{section}" if section else "ms-settings:"
    try:
        subprocess.Popen(["cmd", "/c", "start", "", target],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True, "Abrindo configurações."
    except Exception as exc:
        return False, f"Erro: {exc}"
