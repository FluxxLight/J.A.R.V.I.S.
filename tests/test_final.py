"""PROMPT 4 — versão única, rede, segurança, CLI, autostart, persistência."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from jarvis import __version__
from jarvis.command_engine import intents as I
from jarvis.ui.hub.autostart import default_start_command

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_semver_and_single_source():
    assert __version__.count(".") >= 1
    parts = __version__.split(".")
    assert all(p.isdigit() for p in parts), __version__
    init = (ROOT / "jarvis" / "__init__.py").read_text(encoding="utf-8")
    assert init.count(f'__version__ = "{__version__}"') == 1


def test_cli_version_matches_package():
    result = subprocess.run(
        [sys.executable, "main.py", "--cli", "--version"],
        cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert result.stdout.strip() == __version__


def test_module_entry_propagates_exit_code():
    """`python -m jarvis` deve devolver o mesmo código que main.py."""
    unknown = subprocess.run(
        [sys.executable, "-m", "jarvis", "--cli", "--dry-run",
         "--exec", "xyz comando que nao existe 999"],
        cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert unknown.returncode == 1
    ok = subprocess.run(
        [sys.executable, "-m", "jarvis", "--cli", "--version"],
        cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert ok.returncode == 0 and __version__ in ok.stdout


def test_cli_exposes_fullscreen_and_minimized():
    parser_src = Path(ROOT / "jarvis" / "ui" / "cli.py").read_text(encoding="utf-8")
    assert "--fullscreen" in parser_src
    assert "--minimized" in parser_src
    assert "start_fullscreen" in Path(
        ROOT / "jarvis" / "ui" / "hub" / "hub_window.py").read_text(encoding="utf-8")


FORBIDDEN_MODULES = {
    "requests", "httpx", "aiohttp", "openai", "anthropic", "oai",
    "google.generativeai", "langchain", "llama_cpp", "transformers",
    "websocket", "websockets", "sentry_sdk",
}


def test_no_llm_or_http_client_imports():
    """O núcleo não importa cliente HTTP, LLM ou telemetria."""
    hits = []
    for path in (ROOT / "jarvis").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0], node.module]
            for name in names:
                if name in FORBIDDEN_MODULES or name.split(".")[0] in FORBIDDEN_MODULES:
                    hits.append(f"{path.relative_to(ROOT)}:{node.lineno}:{name}")
    assert hits == []


def test_unknown_text_never_executes_as_shell(app):
    """Texto/voz nunca vira shell: entradas hostis devem ser UNKNOWN/não-executadas."""
    hostile = [
        "rm -rf /",
        "del /f /s C:\\Windows",
        "powershell -enc abc",
        "$(reboot)",
        "`id`",
        "python -c \"import os; os.system('x')\"",
        "; calc.exe",
        "&& notepad",
        "| bash",
        "formato o disco",
        "drop table users",
    ]
    for text in hostile:
        result = app.handle_text(text)
        assert result.executed is False, (text, result)
        assert result.intent in (I.UNKNOWN, ""), (text, result)
        assert result.success is False, (text, result)
        # nunca vira OpenApplication com o binário citado
        assert result.action_id != "OpenApplication" or not result.executed


def test_url_intent_is_not_shell(app):
    """Uma URL na frase pode abrir o navegador (ação autorizada), nunca 'curl'/'wget'."""
    result = app.handle_text("curl http://example.com")
    assert result.action_id != "OpenApplication"
    if result.intent == "OPEN_URL":
        assert result.params.get("url", "").startswith("http")
        assert "curl" not in (result.params.get("app") or "")


def test_voice_hostile_same_as_text(app):
    result_text = app.handle_text("formato o disco")
    trace = app.handle_voice_transcript("jarvis, formato o disco")
    assert result_text.executed is False
    assert trace.engine_result is not None
    assert trace.engine_result.executed is False
    assert trace.command_after_wake  # wake word não comeu o comando


def test_default_start_command_points_at_main():
    cmd = default_start_command()
    assert "--hub" in cmd
    assert "main.py" in cmd
    # o arquivo citado existe de verdade (não é caminho inventado)
    quoted = [p.strip('"') for p in cmd.split('"') if p.strip() and not p.strip().startswith("--")]
    mains = [p for p in quoted if p.endswith("main.py")]
    assert mains, cmd
    assert Path(mains[0]).is_file()


def test_settings_theme_and_intro_survive_restart(data_dir):
    from jarvis.core.app import JarvisApp
    app = JarvisApp(data_dir=data_dir, dry_run=True)
    app.start()
    assert app.settings.set("ui.theme", "vermelho")
    assert app.settings.set("intro.enabled", False)
    assert app.settings.set("tts.volume", 0.4)
    app.shutdown()

    app2 = JarvisApp(data_dir=data_dir, dry_run=True)
    app2.start()
    try:
        assert app2.settings.get("ui.theme") == "vermelho"
        assert app2.settings.get("intro.enabled") is False
        assert app2.settings.get("tts.volume") == 0.4
    finally:
        app2.shutdown()


def test_prompt_examples_text_and_voice(app):
    pairs = [
        ("abra o navegador", "J.A.R.V.I.S., abra o navegador."),
        ("abra a calculadora", "jarvis abra a calculadora"),
        ("abra o bloco de notas", "JARVIS, abra o bloco de notas"),
        ("mostre a hora", "J.A.R.V.I.S., que horas são?"),
        ("mostre a data", "jarvis mostre a data"),
        ("abra o explorador", "J.A.R.V.I.S. abre o explorador"),
    ]
    for text, spoken in pairs:
        r = app.handle_text(text)
        t = app.handle_voice_transcript(spoken)
        assert r.success, text
        assert t.engine_result is not None and t.engine_result.success, spoken
        assert r.intent == t.engine_result.intent != I.UNKNOWN
