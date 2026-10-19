"""AUDITORIA CICLO 4 (PROMPT 4) — finalização: rede, segurança, versão,
layout, persistência, CLI, assets, tentar quebrar o que o 3.4 deixou.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FAIL = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond:
        FAIL.append(name)


# ---------------------------------------------------------------------------
# 1) versão única
# ---------------------------------------------------------------------------
from jarvis import __version__
check("versão semver", __version__.count(".") >= 1 and all(
    p.isdigit() for p in __version__.split(".")), __version__)
init_src = (ROOT / "jarvis" / "__init__.py").read_text(encoding="utf-8")
check("versão declarada uma vez", init_src.count("__version__ = ") == 1)

r = subprocess.run(
    [sys.executable, "main.py", "--cli", "--version"],
    cwd=ROOT, capture_output=True, text=True, timeout=30)
check("--version == __version__", r.returncode == 0 and r.stdout.strip() == __version__,
      r.stdout.strip())

r = subprocess.run(
    [sys.executable, "-m", "jarvis", "--cli", "--version"],
    cwd=ROOT, capture_output=True, text=True, timeout=30)
check("python -m jarvis --version", r.returncode == 0 and __version__ in r.stdout)

r = subprocess.run(
    [sys.executable, "-m", "jarvis", "--cli", "--dry-run",
     "--exec", "comando inexistente xyzzy"],
    cwd=ROOT, capture_output=True, text=True, timeout=45)
check("python -m jarvis propaga exit 1", r.returncode == 1, r.returncode)

# ---------------------------------------------------------------------------
# 2) zero clientes HTTP / LLM
# ---------------------------------------------------------------------------
FORBIDDEN = {"requests", "httpx", "aiohttp", "openai", "anthropic",
             "langchain", "transformers", "websocket", "websockets", "sentry_sdk"}
hits = []
for path in (ROOT / "jarvis").rglob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        for name in names:
            if name in FORBIDDEN:
                hits.append(f"{path.name}:{node.lineno}:{name}")
check("sem cliente HTTP/LLM", hits == [], str(hits[:5]))

# ---------------------------------------------------------------------------
# 3) segurança: texto hostil nunca executa
# ---------------------------------------------------------------------------
from jarvis.core.app import JarvisApp
from jarvis.command_engine import intents as I

data = Path(tempfile.mkdtemp(prefix="audit4-"))
app = JarvisApp(data_dir=data, dry_run=True)
app.start()
hostile_ok = True
for text in ("rm -rf /", "del /f C:\\Windows",
             "powershell -enc aa", "$(reboot)", "; calc", "| bash"):
    result = app.handle_text(text)
    if result.executed or result.intent not in (I.UNKNOWN, ""):
        hostile_ok = False
        print("  hostil passou:", text, result.intent, result.executed)
check("texto hostil = UNKNOWN", hostile_ok)

# wake word preserva o resto mesmo em hostil
trace = app.handle_voice_transcript("J.A.R.V.I.S., rm -rf /")
check("wake+hostil preserva comando",
      trace.wake_detected and "rm" in (trace.command_after_wake or ""),
      repr(trace.command_after_wake))
check("wake+hostil não executa",
      trace.engine_result is not None and trace.engine_result.executed is False)

# exemplos do prompt 4
pairs_ok = True
for text, spoken in (
        ("abra o navegador", "J.A.R.V.I.S., abra o navegador."),
        ("mostre a hora", "jarvis, mostre a hora"),
        ("mostre a data", "JARVIS mostre a data"),
        ("abra o bloco de notas", "jarvis abra o bloco de notas")):
    rt = app.handle_text(text)
    rv = app.handle_voice_transcript(spoken)
    if not (rt.success and rv.engine_result and rv.engine_result.success
            and rt.intent == rv.engine_result.intent):
        pairs_ok = False
        print("  par falhou:", text, rt.intent, getattr(rv.engine_result, "intent", None))
check("pares texto==voz do prompt 4", pairs_ok)

# persistência tema/intro
app.settings.set("ui.theme", "amarelo")
app.settings.set("intro.enabled", False)
app.shutdown()
app2 = JarvisApp(data_dir=data, dry_run=True)
app2.start()
check("tema persiste", app2.settings.get("ui.theme") == "amarelo")
check("intro.enabled persiste", app2.settings.get("intro.enabled") is False)
app2.shutdown()

# ---------------------------------------------------------------------------
# 4) HUB layout + intro sync + flags
# ---------------------------------------------------------------------------
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from jarvis.ui.hub.audio import SfxPlayer
from jarvis.ui.hub.hub_window import HubWindow
from jarvis.ui.hub.settings_ui import SettingsDialog
from jarvis.ui.hub.themes import build_stylesheet, get_theme

qt = QApplication.instance() or QApplication(sys.argv)
core = JarvisApp(data_dir=Path(tempfile.mkdtemp(prefix="audit4h-")), dry_run=True)
core.start()
qt.setStyleSheet(build_stylesheet(get_theme("azul")))
hub = HubWindow(core, sfx=SfxPlayer(enabled=False),
                start_fullscreen=False, start_minimized=False)
hub.show()


def pump(seconds=0.15):
    deadline = time.time() + seconds
    while time.time() < deadline:
        qt.processEvents()
        time.sleep(0.005)


pump(0.2)
layout_ok = True
for w, h in ((800, 600), (1280, 720), (1366, 768), (1920, 1080), (2560, 1440)):
    hub.resize(w, h)
    pump(0.05)
    if hub.nucleus.width() < 80 or hub.nucleus.height() < 80:
        layout_ok = False
        print("  núcleo pequeno em", w, h, hub.nucleus.width(), hub.nucleus.height())
    if w < 1024 and hub._left_col.width() > 220:
        layout_ok = False
        print("  coluna larga em", w, hub._left_col.width())
check("layout 5 resoluções", layout_ok)
check("mínimo do HUB <= 800", hub.minimumWidth() <= 800 and hub.minimumHeight() <= 560)

dialog = SettingsDialog(core, hub)
dialog.show()
pump(0.1)
dialog.intro_check.setChecked(False)
pump(0.05)
check("intro sync Aparência→Inicialização",
      dialog.intro_check_startup.isChecked() is False
      and core.settings.get("intro.enabled") is False)
dialog.intro_check_startup.setChecked(True)
pump(0.05)
check("intro sync Inicialização→Aparência",
      dialog.intro_check.isChecked() is True
      and core.settings.get("intro.enabled") is True)
dialog.close()

# animações aplicam a quente
dialog = SettingsDialog(core, hub)
dialog.show()
pump(0.05)
dialog.anim_check.setChecked(False)
pump(0.05)
check("animações aplicam a quente", hub.nucleus.is_animated() is False)
dialog.close()

# CLI flags existem
cli_src = (ROOT / "jarvis" / "ui" / "cli.py").read_text(encoding="utf-8")
check("CLI --fullscreen", "--fullscreen" in cli_src)
check("CLI --minimized", "--minimized" in cli_src)

# SFX paths existem
from jarvis.ui.hub.audio import sfx_path
from jarvis.ui.hub.sfx import SOUNDS
sfx_ok = all(sfx_path(name) is not None and sfx_path(name).exists()
             for name in SOUNDS)
check("6 SFX locais presentes", sfx_ok, str(list(SOUNDS)))

# autostart aponta para main.py real
from jarvis.ui.hub.autostart import default_start_command
cmd = default_start_command()
check("autostart contém --hub", "--hub" in cmd)
check("autostart main.py existe", "main.py" in cmd and
      any(Path(p.strip('"')).is_file()
          for p in cmd.split() if "main.py" in p))

# fechar limpo
try:
    hub._bridge.detach()
except Exception:
    pass
hub.close()
pump(0.1)
core.shutdown()

print()
print("CICLO 4:", "0 falhas" if not FAIL else f"{len(FAIL)} falhas: {FAIL}")
sys.exit(1 if FAIL else 0)
