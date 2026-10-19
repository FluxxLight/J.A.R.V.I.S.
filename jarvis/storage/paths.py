"""Caminhos de dados locais do J.A.R.V.I.S.

Windows: %APPDATA%/JARVIS
Outros:  ~/.jarvis
Permite override (útil para testes) via `set_base_dir`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_APP_NAME = "JARVIS"
_override: Optional[Path] = None


def set_base_dir(path: Path | str | None) -> None:
    global _override
    _override = Path(path) if path else None


def base_dir() -> Path:
    if _override is not None:
        return _override
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / _APP_NAME
    return Path.home() / ".jarvis"


def ensure_layout(root: Optional[Path] = None) -> dict[str, Path]:
    root = Path(root) if root else base_dir()
    layout = {
        "base": root,
        "logs": root / "logs",
        "models": root / "models",   # modelos locais de voz (ex.: Vosk)
        "backup": root / "backup",   # backups de arquivos corrompidos
    }
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    return layout


def settings_file(root: Optional[Path] = None) -> Path:
    return (Path(root) if root else base_dir()) / "settings.json"


def custom_commands_file(root: Optional[Path] = None) -> Path:
    return (Path(root) if root else base_dir()) / "custom_commands.json"


def memory_file(root: Optional[Path] = None) -> Path:
    return (Path(root) if root else base_dir()) / "memory.json"
