"""Lançador de aplicativos, URLs e pastas (foco Windows, com fallbacks).

NUNCA executa texto arbitrário do usuário como shell: somente alvos
resolvidos pelo catálogo, caminhos validados ou URLs validadas.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from jarvis.logger import get_logger
from jarvis.utils.platform import is_macos, is_windows

log = get_logger("system.launcher")

_URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+|[a-z0-9-]+\.(com|net|org|io|dev|br|app|com\.br)[^\s]*)",
                     re.IGNORECASE)

# Catálogo de apps conhecidos: chave -> candidatos (comando ou caminho Windows).
APP_CATALOG: dict[str, dict[str, list[str]]] = {
    "browser": {
        "win": ["cmd /c start \"\" http://localhost"],
        "exe_names": ["chrome.exe", "msedge.exe", "firefox.exe"],
        "linux": ["xdg-open http://localhost"],
        "mac": ["open http://localhost"],
    },
    "calculator": {
        "win": ["calc.exe"],
        "exe_names": ["calc.exe"],
        "linux": ["gnome-calculator", "kcalc", "xcalc"],
        "mac": ["open -a Calculator"],
    },
    "notepad": {
        "win": ["notepad.exe"],
        "exe_names": ["notepad.exe"],
        "linux": ["gedit", "kate", "mousepad", "xed"],
        "mac": ["open -a TextEdit"],
    },
    "explorer": {
        "win": ["explorer.exe"],
        "exe_names": ["explorer.exe"],
        "linux": ["xdg-open ~"],
        "mac": ["open ~"],
    },
    "discord": {
        "win": ["Discord.exe"],
        "exe_names": ["Discord.exe", "DiscordPTB.exe", "DiscordCanary.exe"],
        "linux": ["discord"],
        "mac": ["open -a Discord"],
    },
}


def extract_url(text: str) -> Optional[str]:
    """Extrai a primeira URL de um texto livre."""
    match = _URL_RE.search(text or "")
    if not match:
        return None
    url = match.group(1).rstrip(".,;:!?)\"'")
    if not url.lower().startswith("http"):
        url = "http://" + url
    try:
        parsed = urlparse(url)
        if not parsed.netloc or "." not in parsed.netloc:
            return None
    except Exception:
        return None
    return url


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def open_url(url: str) -> Tuple[bool, str]:
    if not is_valid_url(url):
        return False, f"URL inválida: {url}"
    try:
        webbrowser.open(url, new=2)
        log.info("URL aberta: %s", url)
        return True, f"Abrindo {url}."
    except Exception as exc:
        log.exception("Falha ao abrir URL")
        return False, f"Não consegui abrir a URL: {exc}"


def open_folder(path_str: str) -> Tuple[bool, str]:
    try:
        folder = Path(os.path.expandvars(os.path.expanduser(path_str))).resolve()
    except Exception:
        return False, "Caminho inválido."
    if not folder.exists():
        return False, f"Pasta não encontrada: {folder}"
    target = folder if folder.is_dir() else folder.parent
    try:
        if is_windows():
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif is_macos():
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        log.info("Pasta aberta: %s", target)
        return True, "Abrindo pasta."
    except Exception as exc:
        log.exception("Falha ao abrir pasta")
        return False, f"Não consegui abrir a pasta: {exc}"


def _run_detached_win(command: str) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if command.startswith("cmd /c start"):
        subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags)
    else:
        try:
            subprocess.Popen([command], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=flags)
        except FileNotFoundError:
            # tenta via shell (resolve App Paths / PATH)
            subprocess.Popen(f'start "" "{command}"', shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=flags)


def resolve_app_target(app_key: str, custom_path: str = "") -> Optional[str]:
    """Resolve app_key do catálogo (ou caminho personalizado) para um alvo."""
    key = (app_key or "").strip().lower()
    if custom_path:
        candidate = Path(os.path.expandvars(os.path.expanduser(custom_path)))
        if candidate.exists():
            return str(candidate)
        if shutil.which(custom_path):
            return custom_path
        log.warning("Caminho personalizado inválido para '%s': %s", key, custom_path)
    entry = APP_CATALOG.get(key)
    if not entry:
        # permite executável direto se existir no PATH (ex.: "code", "spotify")
        if shutil.which(key):
            return key
        return None
    if is_windows():
        for exe in entry.get("exe_names", []):
            found = shutil.which(exe)
            if found:
                return found
        return entry["win"][0]
    if is_macos():
        return entry["mac"][0]
    for cmd in entry.get("linux", []):
        name = cmd.split()[0]
        if shutil.which(name) or cmd.startswith("xdg-open"):
            return cmd
    return entry["linux"][0] if entry.get("linux") else None


def open_app(app_key: str, custom_path: str = "") -> Tuple[bool, str]:
    if app_key.strip().lower() == "browser":
        return open_url("http://localhost")
    target = resolve_app_target(app_key, custom_path)
    if not target:
        return False, f"Aplicativo desconhecido ou não instalado: {app_key}"
    try:
        if is_windows():
            _run_detached_win(target)
        elif target.startswith(("open ", "xdg-open ")):
            subprocess.Popen(target.split(), stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen([target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info("App aberto: %s (%s)", app_key, target)
        return True, f"Abrindo {app_key}."
    except FileNotFoundError:
        return False, f"Aplicativo não encontrado: {app_key}"
    except PermissionError:
        return False, f"Sem permissão para abrir: {app_key}"
    except Exception as exc:
        log.exception("Falha ao abrir app")
        return False, f"Não consegui abrir {app_key}: {exc}"
