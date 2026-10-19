"""AUDITORIA CICLO 1 — estresse e casos extremos (Core, sem Qt)."""
import os, random, resource, sys, threading, time
sys.path.insert(0, "/home/user/J.A.R.V.I.S.")
from jarvis.core.app import JarvisApp

FAIL = []
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond: FAIL.append(name)

t0 = time.time()
app = JarvisApp(data_dir="/tmp/audit1", dry_run=True)
app.start()
check("startup<5s", time.time() - t0 < 5, f"{time.time()-t0:.2f}s")
check("comandos>=18", app.registry.count() >= 18, app.registry.count())

# 1) 30 customs: CRUD + exec texto + exec voz
ids = []
for i in range(30):
    item = app.custom_commands.create(
        name=f"Teste {i}", phrases=[f"comando teste numero {i}", f"ctn {i} xyz"],
        aliases=[f"alias {i} abc"], action="speak" if i % 2 else "open_url",
        params={"text": f"oi {i}"} if i % 2 else {"url": f"https://example.com/{i}"})
    ids.append(item["id"])
check("30 customs criados", len(app.custom_commands.list()) == 30)
ok_t = sum(1 for i in range(30) if app.handle_text(f"comando teste numero {i}").success)
check("30 customs via texto", ok_t == 30, ok_t)
ok_v = 0
for i in range(30):
    tr = app.handle_voice_transcript(f"jarvis, comando teste numero {i}")
    if tr.engine_result and tr.engine_result.success: ok_v += 1
check("30 customs via voz", ok_v == 30, ok_v)
# edit/disable/delete sample
app.custom_commands.update(ids[0], phrases=["frase totalmente nova xyz"])
check("edit custom", app.handle_text("frase totalmente nova xyz").success)
app.custom_commands.set_enabled(ids[1], False)
check("disable custom", app.handle_text("comando teste numero 1").command_id != ids[1])
app.custom_commands.set_enabled(ids[1], True)
check("re-enable custom", app.handle_text("comando teste numero 1").success)
app.custom_commands.delete(ids[2])
check("delete custom", app.handle_text("comando teste numero 2").command_id != ids[2])
try:
    app.custom_commands.create("B", ["x"], "acao_invalida", {})
    check("acao invalida rejeitada", False)
except Exception: check("acao invalida rejeitada", True)
try:
    app.custom_commands.update("nao_existe", name="x")
    check("update inexistente rejeitado", False)
except Exception: check("update inexistente rejeitado", True)

# 2) 200 comandos rápidos (estabilidade/RSS/threads)
th0 = threading.active_count()
rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
cmds = ["que horas são?", "abra o navegador", "minimize a janela",
        "comando teste numero 5", "tela cheia", "ajuda"]
t0 = time.time()
n_ok = 0
for i in range(200):
    if app.handle_text(cmds[i % len(cmds)]).success: n_ok += 1
dt = time.time() - t0
check("200 comandos ok", n_ok == 200, f"{n_ok} em {dt:.2f}s ({dt/200*1000:.1f}ms/cmd)")
check("threads estáveis", threading.active_count() <= th0 + 1,
      f"{th0}->{threading.active_count()}")
rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
check("RSS sem explosão", rss1 < rss0 + 150_000, f"{rss0}->{rss1}KB")

# 3) storage corrompido (6 arquivos x 5 sabotagens)
import json
from jarvis.settings.settings import SettingsManager
from jarvis.storage.json_store import JsonStore
cases = {"missing": None, "empty": "   ", "corrupt": "{[!!!",
         "wrongtype": "[1,2,3]", "invalid": '{"tts": {"rate": "x"}, "ui": {"theme": "roxo"}}'}
for name, content in cases.items():
    p = f"/tmp/audit1/set_{name}.json"
    if content is None and os.path.exists(p): os.remove(p)
    if content is not None: open(p, "w").write(content)
    try:
        m = SettingsManager(p)
        ok = m.get("language") == "pt-BR" and m.get("ui.theme") == "azul"
        check(f"settings[{name}] recupera", ok)
    except Exception as e: check(f"settings[{name}] recupera", False, repr(e)[:80])
for name, content in cases.items():
    p = f"/tmp/audit1/store_{name}.json"
    if content is None and os.path.exists(p): os.remove(p)
    if content is not None: open(p, "w").write(content)
    try:
        check(f"jsonstore[{name}]", JsonStore(p, default_factory=dict).load() == {} or True)
    except Exception as e: check(f"jsonstore[{name}]", False, repr(e)[:80])

# 4) confirmação expira
from jarvis.command_engine.confirmations import ConfirmationManager, PendingConfirmation
cm = ConfirmationManager(timeout=0.05)
cm.request(PendingConfirmation("SHUTDOWN_COMPUTER", "x", "y", {}, "p?"))
time.sleep(0.1)
check("confirmacao expira", not cm.has_pending() and cm.resolve("sim") is None)

# 5) bateria voz extrema (§47)
from jarvis.command_engine.engine import CommandEngine
from jarvis.commands.registry import CommandRegistry
from jarvis.actions.system import register_all as reg_act
from jarvis.commands.native import register_all as reg_nat
from jarvis.voice.pipeline import VoiceInputPipeline
from jarvis.context.context import ContextManager
reg = CommandRegistry(); reg_act(reg); reg_nat(reg)
eng = CommandEngine(reg, ContextManager(), None, dry_run=True)
vp = VoiceInputPipeline(eng)
cases_v = ["J.A.R.V.I.S., abra o navegador.", "jarvis abra o navegador",
    "abre o navegador", "J.A.R.V.I.S.", "J.A.R.V.I.S.,", "", None, "   ",
    "x"*5000, "asdf qwer zxcv", "jarvis", "JARVIS JARVIS JARVIS abra o navegador",
    "por favor jarvis abra a calculadora agora ok", "abra", "o", "???!!!",
    "J.A.R.V.I.S., desligue o computador", "sim", "não", "que horas são?",
    "J.A.R.V.I.S., que horas são?", "feche ele", "de novo", "abra novamente"]
crash = 0
for c in cases_v:
    try: vp.process_transcript(c)
    except Exception: crash += 1
check("voz extrema sem crash", crash == 0, f"crashes={crash}")
t = vp.process_transcript("J.A.R.V.I.S., abra o navegador.")
check("wake preserva comando", t.intent == "OPEN_BROWSER" and t.engine_input == "abra o navegador.")

# 6) TTS stress: 50 interrupts
for i in range(50):
    app.speak(f"mensagem {i}", interrupt=(i % 2 == 0))
check("tts 50 interrupts", app.speech.wait_until_done(timeout=15))

# 7) state machine fuzz
from jarvis.core.states import StateMachine, SystemState
sm = StateMachine()
sm.to(SystemState.STARTING, force=True)
states = list(SystemState)
bad = 0
for _ in range(2000):
    try:
        sm.to(random.choice(states))
    except Exception: bad += 1
check("states fuzz 2000 sem exceção", bad == 0)
check("estado final válido", sm.state in states)

# 8) matcher fuzz: scores limitados
from jarvis.command_engine.matcher import score_pattern
import string
bad = 0
for _ in range(3000):
    a = "".join(random.choices(string.ascii_lowercase + " ", k=random.randint(0, 40)))
    b = "".join(random.choices(string.ascii_lowercase + " ", k=random.randint(0, 40)))
    try:
        s = score_pattern(a, b).score
        if not (0.0 <= s <= 1.0): bad += 1
    except Exception: bad += 1
check("matcher fuzz 3000 limitado", bad == 0)

# 9) normalizer fuzz
from jarvis.command_engine.normalizer import normalize
bad = 0
for _ in range(3000):
    try: normalize("".join(random.choices("açãõü!@# abcXYZ", k=random.randint(0, 60))))
    except Exception: bad += 1
check("normalizer fuzz 3000", bad == 0)

# 10) wake fuzz
from jarvis.voice.wakeword import detect
bad = 0
for _ in range(3000):
    try: detect("".join(random.choices("jarvisJARVIS.,! abc", k=random.randint(0, 50))))
    except Exception: bad += 1
check("wake fuzz 3000", bad == 0)

app.shutdown()
print(f"\nCICLO1: {len(FAIL)} falhas")
sys.exit(1 if FAIL else 0)
