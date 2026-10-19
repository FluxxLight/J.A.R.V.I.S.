# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec do J.A.R.V.I.S. — one-dir (estabilidade + startup rápido).

Decisão one-dir vs one-file (§42): com Qt6, one-dir evita extração de ~200 MB
a cada início, reduz falsos positivos de antivírus e facilita updates/diag.
Um atalho pode apontar para dist/JARVIS/J.A.R.V.I.S.exe.
"""

import importlib.util
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH)  # noqa: F821 (variável do PyInstaller)

block_cipher = None

# Dependências opcionais de voz: empacota SE instaladas no build.
voice_hidden = [m for m in ("vosk", "sounddevice", "pyttsx3", "_sounddevice",
                             "cffi")
                if importlib.util.find_spec(m) is not None]
print("hiddenimports de voz incluídos:", voice_hidden)

sfx_src = str(ROOT / "jarvis" / "ui" / "hub" / "assets")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(sfx_src, "jarvis/ui/hub/assets")] if Path(sfx_src).exists() else [],
    hiddenimports=[
        "PySide6.QtNetwork",      # single instance (QLocalServer)
        "PySide6.QtMultimedia",   # SFX (QSoundEffect)
        *voice_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "setuptools", "pip"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_path = os.environ.get("JARVIS_ICON") or None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="J.A.R.V.I.S",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX em Qt costuma gerar falso positivo de AV; desligado
    console=False,  # app desktop (HUB); sem console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JARVIS",
)
