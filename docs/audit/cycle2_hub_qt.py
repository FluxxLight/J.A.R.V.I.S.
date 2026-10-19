"""AUDITORIA CICLO 2 — UI/Qt sob estresse (offscreen)."""
import shutil, sys, time
sys.path.insert(0, "/home/user/J.A.R.V.I.S.")
shutil.rmtree("/tmp/audit2", ignore_errors=True)
from PySide6.QtWidgets import QApplication
from jarvis.core.app import JarvisApp
from jarvis.ui.hub.audio import SfxPlayer
from jarvis.ui.hub.hub_window import HubWindow
from jarvis.ui.hub.themes import THEME_ORDER, build_stylesheet, get_theme

FAIL = []
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond: FAIL.append(name)

def pump(qt, s=0.15):
    d = time.time() + s
    while time.time() < d:
        qt.processEvents(); time.sleep(0.005)

def wait(pred, qt, timeout=12):
    d = time.time() + timeout
    while time.time() < d:
        qt.processEvents()
        try:
            if pred(): return True
        except Exception: pass
        time.sleep(0.02)
    return False

qt = QApplication(sys.argv)
t0 = time.time()
app = JarvisApp(data_dir="/tmp/audit2", dry_run=True)
app.start()
check("core startup<5s", time.time() - t0 < 5, f"{time.time()-t0:.2f}s")
qt.setStyleSheet(build_stylesheet(get_theme("azul")))
t0 = time.time()
hub = HubWindow(app, sfx=SfxPlayer(enabled=False))
hub.resize(1440, 860); hub.show(); pump(qt, 0.5)
check("hub open<5s", time.time() - t0 < 5, f"{time.time()-t0:.2f}s")

# 1) temas x30 cruzando estados
from jarvis.core.states import SystemState
bad = 0
for i in range(30):
    try:
        st = [SystemState.IDLE, SystemState.LISTENING, SystemState.PROCESSING,
              SystemState.EXECUTING, SystemState.SPEAKING, SystemState.ERROR][i % 6]
        hub.nucleus.set_state(st.value)
        hub.apply_theme(THEME_ORDER[i % 5], persist=False)
        pump(qt, 0.03)
        hub.nucleus.grab(); hub.state_badge.grab()
    except Exception: bad += 1
check("30 temas x estados", bad == 0, f"erros={bad}")
hub.nucleus.set_state("IDLE"); hub.apply_theme("azul", persist=False)

# 2) F11 x20
bad = 0
for i in range(20):
    try:
        hub.toggle_fullscreen(); pump(qt, 0.03)
        assert hub.isFullScreen() == (i % 2 == 0)
    except Exception: bad += 1
check("F11 x20", bad == 0 and not hub.isFullScreen())

# 3) 30 comandos via workers do HUB + busy guard
ok = 0
for i in range(30):
    hub.input.setText("que horas são?" if i % 2 == 0 else "tela cheia")
    hub.submit_text()
    hub.submit_text()  # 2o deve ser ignorado (busy)
    if wait(lambda: not hub._busy, qt): ok += 1
check("30 cmds via hub workers", ok == 30, ok)
check("badge final EM ESPERA", hub.state_badge.text() == "EM ESPERA", hub.state_badge.text())

# 4) abrir/fechar diálogos x10
from jarvis.ui.hub.settings_ui import SettingsDialog
from jarvis.ui.hub.commands_ui import CommandsDialog
bad = 0
for _ in range(10):
    try:
        d1 = SettingsDialog(app, hub); d1.show(); pump(qt, 0.03); d1.close(); d1.deleteLater()
        d2 = CommandsDialog(app, hub); d2.show(); pump(qt, 0.03); d2.close(); d2.deleteLater()
        pump(qt, 0.03)
    except Exception: bad += 1
check("diálogos x10", bad == 0, f"erros={bad}")

# 5) intro skip x5
from jarvis.ui.hub.intro import IntroWindow
bad = 0
for _ in range(5):
    try:
        w = IntroWindow(theme=get_theme("verde"), sfx=None)
        w.show(); w.start(); pump(qt, 0.2); w.skip()
        if not wait(lambda: not w.isVisible(), qt, 5): bad += 1
        w.deleteLater(); pump(qt, 0.05)
    except Exception: bad += 1
check("intro skip x5", bad == 0)

# 6) nucleus: 5 temas x 7 estados renderizam
from jarvis.ui.hub.nucleus import NucleusWidget
n = NucleusWidget(); n.resize(300, 300); n.show(); pump(qt, 0.2)
bad = 0
for tid in THEME_ORDER:
    n.set_theme(get_theme(tid))
    for st in ("IDLE","LISTENING","PROCESSING","EXECUTING","SPEAKING","READY","ERROR"):
        try:
            n.set_state(st); n.set_frozen_time(1.5); pump(qt, 0.02)
            assert not n.grab().isNull()
        except Exception: bad += 1
check("nucleus 5x7 renders", bad == 0)
# perf de paint
n.set_frozen_time(None); pump(qt, 0.1)
t0 = time.time(); K = 40
for _ in range(K):
    n.repaint()
paint_ms = (time.time() - t0) / K * 1000
check("paint<=33ms (30fps+)", paint_ms <= 33, f"{paint_ms:.1f}ms")
n.deleteLater()

# 7) ciclo de vida: 5 hubs abrir/fechar + evento após close não crasha
bad = 0
for i in range(5):
    try:
        h = HubWindow(app, sfx=SfxPlayer(enabled=False))
        h.show(); pump(qt, 0.1)
        h._bridge.detach(); h.deleteLater(); pump(qt, 0.1)
    except Exception: bad += 1
try:
    app.states.to(SystemState.LISTENING); pump(qt, 0.1)
    app.states.to(SystemState.IDLE); pump(qt, 0.1)
except Exception: bad += 1
check("5 hubs lifecycle", bad == 0)

# 8) CommandDialog: 10 válidos + 10 inválidos
from jarvis.ui.hub.commands_ui import CommandDialog
ok_v = ok_i = 0
for i in range(10):
    d = CommandDialog()
    d.name_edit.setText(f"C{i}"); d.phrases_edit.setPlainText(f"frase val {i} zz")
    d.action_combo.setCurrentIndex(d.action_combo.findData("open_url"))
    d._param_edits["url"].setText(f"https://example.com/{i}")
    d._on_save()
    if d.result_item: ok_v += 1
    d2 = CommandDialog()
    d2.name_edit.setText("")
    d2.phrases_edit.setPlainText("")
    d2._on_save()
    if d2.result_item is None and d2.error_label.text(): ok_i += 1
check("dialog 10 validos", ok_v == 10)
check("dialog 10 invalidos bloqueados", ok_i == 10)

# 9) autostart fake x20
from jarvis.ui.hub.autostart import AutostartManager, MemoryBackend
m = AutostartManager(MemoryBackend())
bad = 0
for i in range(20):
    en = i % 2 == 0
    okk, _ = m.set_enabled(en, '"e" --hub')
    if not okk or m.is_enabled() != en: bad += 1
check("autostart x20", bad == 0)

# 10) diagnostics x10
from jarvis.ui.hub.diagnostics import run_diagnostics
bad = sum(1 for _ in range(10) if len(run_diagnostics(app)) != 10)
check("diagnostics x10", bad == 0)

# 11) resoluções + fullscreen grabs
bad = 0
for w, h in ((1280,720),(1366,768),(1920,1080),(2560,1440)):
    try:
        hub.resize(w, h); pump(qt, 0.15)
        px = hub.grab()
        assert px.width() == w and px.height() == h, (px.width(), px.height())
    except Exception as e: bad += 1; print("   res fail:", w, h, str(e)[:60])
check("4 resoluções", bad == 0)
hub.resize(1440, 860); pump(qt, 0.2)

# 12) settings corrompido -> hub novo ainda abre
open("/tmp/audit2/settings.json", "w").write("{corrompido!")
try:
    app2 = JarvisApp(data_dir="/tmp/audit2", dry_run=True); app2.start()
    h2 = HubWindow(app2, sfx=SfxPlayer(enabled=False)); h2.show(); pump(qt, 0.3)
    ok = h2._theme.id == "azul"
    h2._bridge.detach(); h2.deleteLater(); pump(qt, 0.1); app2.shutdown()
    check("hub com settings corrompido", ok)
except Exception as e: check("hub com settings corrompido", False, str(e)[:80])

# 13) tempestade de eventos: 500 transições
bad = 0
seq = [SystemState.LISTENING, SystemState.PROCESSING, SystemState.EXECUTING,
       SystemState.SPEAKING, SystemState.READY, SystemState.IDLE]
try:
    for i in range(500):
        app.states.to(seq[i % len(seq)], force=True)
        if i % 50 == 0: pump(qt, 0.01)
    pump(qt, 0.3)
    if hub.state_badge.text() not in ("EM ESPERA","PRONTO","OUVINDO","PROCESSANDO","EXECUTANDO","FALANDO"):
        bad += 1
except Exception: bad += 1
check("500 eventos", bad == 0, hub.state_badge.text())

hub._bridge.detach(); hub.deleteLater(); pump(qt, 0.2)
app.shutdown()
print(f"\nCICLO2: {len(FAIL)} falhas")
sys.exit(1 if FAIL else 0)
