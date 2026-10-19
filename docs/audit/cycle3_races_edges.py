"""AUDITORIA CICLO 3 — corrida, interrupção, estados impossíveis, assets."""
import json, os, shutil, sys, threading, time
sys.path.insert(0, "/home/user/J.A.R.V.I.S.")
shutil.rmtree("/tmp/audit3", ignore_errors=True)
shutil.rmtree("/tmp/audit3cli", ignore_errors=True)
from PySide6.QtWidgets import QApplication

FAIL = []
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond: FAIL.append(name)

def pump(qt, s=0.1):
    d = time.time() + s
    while time.time() < d:
        qt.processEvents(); time.sleep(0.005)

qt = QApplication(sys.argv)
from jarvis.core.app import JarvisApp
from jarvis.ui.hub.audio import SfxPlayer
from jarvis.ui.hub.hub_window import HubWindow
from jarvis.ui.hub.themes import build_stylesheet, get_theme

app = JarvisApp(data_dir="/tmp/audit3", dry_run=True)
app.start()
qt.setStyleSheet(build_stylesheet(get_theme("azul")))

# 1) fechar HUB durante worker ativo (não pode travar)
hub = HubWindow(app, sfx=SfxPlayer(enabled=False))
hub.show(); pump(qt, 0.2)
hub.input.setText("que horas são?")
hub.submit_text()
t0 = time.time()
hub.close(); pump(qt, 0.5)
check("close durante worker <6s", time.time() - t0 < 6, f"{time.time()-t0:.2f}s")

# app foi shutdown pelo close; novo ciclo
app = JarvisApp(data_dir="/tmp/audit3", dry_run=True)
app.start()
hub = HubWindow(app, sfx=SfxPlayer(enabled=False))
hub.show(); pump(qt, 0.2)

# 2) handlers do EventBus voltam ao baseline após fechar hub
from jarvis.core import events as EV
def n_handlers():
    return sum(len(v) for v in app.events._handlers.values())
base = n_handlers()
h2 = HubWindow(app, sfx=SfxPlayer(enabled=False))
mid = n_handlers()
h2._bridge.detach(); h2.deleteLater(); pump(qt, 0.2)
check("handlers sem vazamento", mid > base and n_handlers() == base, f"{base}->{mid}->{n_handlers()}")

# 3) assets: some com 1 wav -> play falha com elegância
from jarvis.ui.hub import sfx as SFX
p = SFX.ASSETS_DIR / "tick.wav"
bak = p.with_suffix(".wav.bak")
p.rename(bak)
try:
    pl = SfxPlayer(enabled=True)
    r = pl.play("tick")
    check("sfx ausente sem crash", r is False)
finally:
    bak.rename(p)

# 4) troca de backend TTS em runtime + fala
from jarvis.voice.tts import NullTTS
try:
    app.speech.set_tts(NullTTS("teste"))
    app.speak("troca de backend")
    check("tts swap runtime", app.speech.wait_until_done(timeout=10))
except Exception as e: check("tts swap runtime", False, str(e)[:60])

# 5) settings concorrente x10 threads
errs = []
def wset(i):
    try:
        for j in range(20):
            app.settings.set("tts.rate", 150 + (i + j) % 50)
    except Exception as e: errs.append(e)
ths = [threading.Thread(target=wset, args=(i,)) for i in range(10)]
[t.start() for t in ths]; [t.join(timeout=30) for t in ths]
try:
    json.load(open("/tmp/audit3/settings.json"))
    valid = True
except Exception: valid = False
check("settings concorrente", not errs and valid and all(not t.is_alive() for t in ths))

# 6) memória concorrente
errs = []
def wmem(i):
    try:
        for j in range(50):
            app.memory.record_execution("GET_TIME", f"t{i}-{j}", True)
    except Exception as e: errs.append(e)
ths = [threading.Thread(target=wmem, args=(i,)) for i in range(10)]
[t.start() for t in ths]; [t.join(timeout=60) for t in ths]
check("memory concorrente", not errs, f"erros={len(errs)}")

# 7) engine concorrente (comandos seguros)
errs = []
def weng(i):
    try:
        for j in range(20):
            r = app.engine.process("que horas são?", source="text")
            if not r.success: errs.append("fail")
    except Exception as e: errs.append(e)
ths = [threading.Thread(target=weng, args=(i,)) for i in range(10)]
[t.start() for t in ths]; [t.join(timeout=60) for t in ths]
check("engine concorrente", not errs, f"erros={len(errs)}")

# 8) hub: texto vazio / espaços / gigante
try:
    hub.input.setText("   "); hub.submit_text(); pump(qt, 0.2)
    hub.input.setText("x" * 10000); hub.submit_text()
    d = time.time() + 10
    while hub._busy and time.time() < d: pump(qt, 0.05)
    check("hub entradas absurdas", not hub._busy)
except Exception as e: check("hub entradas absurdas", False, str(e)[:60])

# 9) tempestade de transcrições
bad = 0
for i in range(100):
    try:
        prefix = "jarvis, " if i % 2 == 0 else ""
        app.handle_voice_transcript(prefix + ("que horas são?" if i % 3 else "abra o navegador"))
    except Exception: bad += 1
check("100 transcrições", bad == 0)

# 10) TTL de contexto
from jarvis.context.context import ContextManager, Interaction
cx = ContextManager(ttl=0.05)
cx.push(Interaction("abra o discord", "abrir o discord", "OPEN_APP", app="discord"))
time.sleep(0.1)
check("contexto expira", cx.last() is None and not cx.resolve("feche ele").applied)

# 11) nativo removido -> UNKNOWN honesto; ação ausente -> erro honesto
reg = app.registry
cmd = reg.get("native.open_browser")
reg.unregister("native.open_browser")
r = app.engine.process("abra o navegador")
check("comando removido = UNKNOWN", r.intent != "OPEN_BROWSER" or not r.success, r.intent)
reg.register(cmd)
from jarvis.commands.base import Command
reg.register(Command(id="bad", intent="BAD", name="bad", phrases=["frase unica zzz qqq"],
                     action_id="NoSuchAction"))
r = app.engine.process("frase unica zzz qqq")
check("ação ausente honesta", not r.success and "ausente" in r.message.lower(), r.message[:50])
reg.unregister("bad")

# 12) data_dir com espaço/unicode
try:
    a2 = JarvisApp(data_dir="/tmp/audit dir çãõ", dry_run=True)
    a2.start(); a2.handle_text("que horas são?"); a2.shutdown()
    check("data_dir unicode/espaço", True)
except Exception as e: check("data_dir unicode/espaço", False, str(e)[:60])

# 13) entry points exit codes
import subprocess
env = dict(os.environ)
base_cmd = [sys.executable, "main.py", "--cli", "--data-dir", "/tmp/audit3cli", "--dry-run"]
r = subprocess.run(base_cmd + ["--version"], capture_output=True, text=True, cwd="/home/user/J.A.R.V.I.S.", env=env, timeout=60)
from jarvis import __version__ as _VER
check("--version exit 0", r.returncode == 0 and _VER in r.stdout, r.stdout.strip()[:20])
r = subprocess.run(base_cmd + ["--exec", "que horas são?"], capture_output=True, text=True, cwd="/home/user/J.A.R.V.I.S.", env=env, timeout=60)
check("--exec exit 0", r.returncode == 0)
r = subprocess.run(base_cmd + ["--exec", "xyz blargh impossivel"], capture_output=True, text=True, cwd="/home/user/J.A.R.V.I.S.", env=env, timeout=60)
check("--exec desconhecido exit 1", r.returncode == 1, r.returncode)
r = subprocess.run(base_cmd + ["--test-voice", "jarvis, abra o navegador"], capture_output=True, text=True, cwd="/home/user/J.A.R.V.I.S.", env=env, timeout=60)
check("--test-voice exit 0", r.returncode == 0 and "OPEN_BROWSER" in r.stdout)

# 14) SpeechQueue: shutdown duplo + speak pós-shutdown
from jarvis.voice.queue import SpeechQueue
try:
    q = SpeechQueue(NullTTS())
    q.shutdown(wait=True); q.shutdown(wait=True)
    check("queue shutdown idempotente + speak=False", q.speak("oi") is False)
except Exception as e: check("queue shutdown idempotente", False, str(e)[:60])

# 15) mic/reconhecedor indisponíveis: sem crash
from jarvis.voice.microphone import MicrophoneManager
from jarvis.voice.recognizer import create_recognizer
try:
    m = MicrophoneManager()
    devs = m.list_devices()
    st = m.open_stream()
    rec = create_recognizer()
    tr = rec.listen_once(m, timeout=0.5)
    check("mic/rec indisponíveis", st is None and tr.text == "" and not rec.is_ready())
except Exception as e: check("mic/rec indisponíveis", False, str(e)[:60])

# 16) show_and_focus x10 + QSS x20
try:
    for _ in range(10): hub.show_and_focus()
    for tid in (["azul","vermelho","verde","amarelo","cinza"] * 4):
        qt.setStyleSheet(build_stylesheet(get_theme(tid)))
        pump(qt, 0.01)
    check("focus x10 + qss x20", True)
except Exception as e: check("focus x10 + qss x20", False, str(e)[:60])

# 17) make_icon todos os tamanhos + diálogo de comando vazio
from jarvis.ui.hub.app_qt import make_icon
try:
    for size in (16, 32, 48, 64, 128, 256):
        px = make_icon(get_theme("amarelo"), size).pixmap(size, size)
        assert not px.isNull() and px.width() == size
    from jarvis.ui.hub.commands_ui import CommandDialog
    d = CommandDialog()
    d._on_save()
    check("icons + dialog vazio bloqueia", d.result_item is None)
except Exception as e: check("icons + dialog", False, str(e)[:60])

# 18) intro start duplo + skip sem start
from jarvis.ui.hub.intro import IntroWindow
try:
    w = IntroWindow(theme=get_theme("azul"), sfx=None)
    w.show(); w.start(); w.start(); pump(qt, 0.2); w.skip()
    d = time.time() + 5
    while w.isVisible() and time.time() < d: pump(qt, 0.05)
    w2 = IntroWindow(theme=get_theme("azul"), sfx=None)
    w2.show(); pump(qt, 0.1); w2.skip()
    d = time.time() + 5
    while w2.isVisible() and time.time() < d: pump(qt, 0.05)
    check("intro start duplo/skip", not w.isVisible() and not w2.isVisible())
except Exception as e: check("intro start duplo/skip", False, str(e)[:60])

hub._bridge.detach(); hub.deleteLater(); pump(qt, 0.2)
app.shutdown()
shutil.rmtree("/tmp/audit dir çãõ", ignore_errors=True)
print(f"\nCICLO3: {len(FAIL)} falhas")
sys.exit(1 if FAIL else 0)
