"""Build reproduzível do J.A.R.V.I.S. (Windows + verificação cruzada).

Passos (§40):
 1. verificar Python      2. verificar dependências   3. limpar build anterior
 4. executar testes       5. compilar/empacotar       6. incluir assets
 7. preparar pasta models 8. incluir arquivos extras  9. gerar o EXE
 10. verificar o resultado

Uso (no Windows):
    python build.py              # build completo (one-dir)
    python build.py --skip-tests # emergência (não recomendado)
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MIN_PYTHON = (3, 10)
EXE_NAME = "J.A.R.V.I.S.exe"
DIST_DIRNAME = "JARVIS"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ROOT, **kwargs)


def step(number: int, title: str) -> None:
    print(f"\n{'=' * 60}\n[{number}/10] {title}\n{'=' * 60}")


def fail(message: str) -> int:
    print(f"\nFALHA: {message}")
    return 1


def main(argv: list[str]) -> int:
    skip_tests = "--skip-tests" in argv

    step(1, "Verificando Python")
    print("Python:", sys.version)
    if sys.version_info < MIN_PYTHON:
        return fail(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ necessário.")
    if os.name != "nt":
        print("AVISO: build de EXE suportado apenas no Windows. "
              "Continuando em modo verificação (sem PyInstaller).")

    step(2, "Verificando dependências")
    missing = [m for m in ("PySide6", "PyInstaller")
               if importlib.util.find_spec(m) is None]
    if missing and os.name == "nt":
        return fail(f"Dependências ausentes: {missing}. "
                    " Rode: pip install -r requirements-ui.txt "
                    "-r requirements-build.txt")
    if missing:
        print("Ausentes (modo verificação):", missing)
    voice = {m: importlib.util.find_spec(m) is not None
             for m in ("vosk", "sounddevice", "pyttsx3")}
    print("Voz local no build:", voice)
    if os.name == "nt" and not all(voice.values()):
        print("AVISO: dependências de voz ausentes — o EXE sairá sem "
              "reconhecimento/TTS (modo texto). Para voz completa: "
              "pip install -r requirements-voice.txt")

    step(3, "Limpando build anterior")
    for folder in ("build", "dist"):
        path = ROOT / folder
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            print("removido:", path)

    step(4, "Executando testes")
    if skip_tests:
        print("PULADO (--skip-tests).")
    else:
        result = _run([sys.executable, "-m", "pytest", "tests/", "-q"])
        if result.returncode != 0:
            return fail("Testes falharam. Corrija antes do build.")

    step(5, "Gerando ícone do executável")
    icon = ROOT / "build" / "jarvis.ico"
    icon.parent.mkdir(parents=True, exist_ok=True)
    code = (
        "import sys; sys.path.insert(0, r'%s');"
        "from PySide6.QtWidgets import QApplication;"
        "app = QApplication([]);"
        "from jarvis.ui.hub.app_qt import make_icon;"
        "from jarvis.ui.hub.themes import get_theme;"
        "ok = make_icon(get_theme('azul'), 128).pixmap(128,128)"
        ".save(r'%s', 'ICO');"
        "print('icon ok' if ok else 'icon FAIL'); sys.exit(0 if ok else 1)"
        % (ROOT, icon)
    )
    env = dict(os.environ)
    if os.name != "nt":
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = _run([sys.executable, "-c", code], env=env)
    if result.returncode != 0:
        print("AVISO: ícone não gerado — build seguirá sem ícone customizado.")
        icon = None
    else:
        print("ícone:", icon, f"({icon.stat().st_size} bytes)")
    if icon is not None:
        os.environ["JARVIS_ICON"] = str(icon)

    if os.name != "nt":
        _write_build_info(ROOT / "build", voice, exe_path=None)
        print("\nModo verificação concluído (fora do Windows não há EXE).")
        print("No Windows, o build continuaria: PyInstaller -> dist/JARVIS/J.A.R.V.I.S.exe.")
        return 0

    step(6, "Empacotando com PyInstaller (assets via jarvis.spec)")
    result = _run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                   "jarvis.spec"])
    if result.returncode != 0:
        return fail("PyInstaller falhou.")

    step(7, "Preparando pasta de modelos")
    exe_dir = ROOT / "dist" / DIST_DIRNAME
    models = exe_dir / "models"
    models.mkdir(parents=True, exist_ok=True)
    (models / "LEIA-ME.txt").write_text(
        "Coloque aqui um modelo Vosk pt-BR (ex.: pasta vosk-model-small-pt-0.3).\n"
        "O J.A.R.V.I.S. também aceita %APPDATA%\\JARVIS\\models\\vosk.\n"
        "Sem modelo, o app funciona em modo texto + voz simulada.\n",
        encoding="utf-8")

    step(8, "Incluindo arquivos extras")
    for name in ("README.md",):
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, exe_dir / name)
            print("copiado:", name)

    step(9, "Verificando o EXE")
    exe = exe_dir / EXE_NAME
    if not exe.exists():
        return fail(f"EXE não gerado: {exe}")
    size_mb = exe.stat().st_size / 1_000_000
    print(f"EXE: {exe} ({size_mb:.1f} MB)")
    _write_build_info(exe_dir, voice, exe_path=exe)

    step(10, "Smoke test do EXE (--version)")
    try:
        result = _run([str(exe), "--cli", "--version"], capture_output=True,
                      text=True, timeout=60)
        print("saída:", (result.stdout or "").strip()[:80]
              or "(sem stdout — EXE windowed, console=False)")
        if result.returncode != 0:
            return fail("EXE não respondeu a --version.")
    except subprocess.TimeoutExpired:
        return fail("EXE travou no smoke test.")

    print("\nBUILD CONCLUÍDO:", exe_dir)
    return 0


def _write_build_info(target_dir: Path, voice: dict, exe_path: Path | None) -> None:
    """Grava BUILD_INFO.txt na pasta de distribuição (ou build/ em verificação)."""
    from jarvis import __version__
    target_dir.mkdir(parents=True, exist_ok=True)
    voice_line = ", ".join(f"{k}={'sim' if v else 'não'}" for k, v in voice.items())
    exe_line = str(exe_path) if exe_path else "N/A (modo verificação — gere no Windows)"
    text = (
        f"J.A.R.V.I.S. v{__version__}\n"
        f"built_utc={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"python={sys.version.split()[0]}\n"
        f"platform={sys.platform}\n"
        f"voice={voice_line}\n"
        f"exe={exe_line}\n"
        f"layout=one-dir dist/JARVIS/ + _internal/\n"
        f"offline=yes\n"
        f"llm=none\n"
    )
    path = target_dir / "BUILD_INFO.txt"
    path.write_text(text, encoding="utf-8")
    print("BUILD_INFO:", path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
