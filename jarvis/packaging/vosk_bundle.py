"""Localiza o pacote Vosk instalado e lista o que o PyInstaller deve copiar.

O `vosk/__init__.py` faz, no import:

    dlldir = dirname(__file__)
    os.add_dll_directory(dlldir)          # Windows: a PASTA precisa existir
    ffi.dlopen(join(dlldir, "libvosk.dll"))

No EXE one-dir o PyInstaller coloca o .py no PYZ e, por padrão, NÃO cria
`_internal/vosk/` no disco. Resultado: WinError 2 em add_dll_directory.

Solução: copiar o diretório inteiro do pacote para `_internal/vosk/`,
preservando libvosk.dll (e DLLs companheiras) ao lado do __init__.py.
Caminhos relativos — nunca absolutos da máquina de build.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

NATIVE_SUFFIXES = {".dll", ".so", ".dylib", ".pyd"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".egg-info"}

BundleItem = Tuple[str, str, str]  # (src_abs, dest_dir_in_bundle, kind)


def vosk_package_dir() -> Optional[Path]:
    """Pasta real do pacote `vosk` no Python atual, ou None se não instalado."""
    spec = importlib.util.find_spec("vosk")
    if spec is None:
        return None
    locations = list(spec.submodule_search_locations or [])
    if locations:
        path = Path(locations[0])
        if path.is_dir():
            return path
    if spec.origin:
        path = Path(spec.origin).parent
        if path.is_dir():
            return path
    return None


def iter_vosk_files(pkg_dir: Optional[Path] = None) -> Iterable[Path]:
    root = pkg_dir or vosk_package_dir()
    if root is None or not root.is_dir():
        return []
    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.name.startswith("."):
            continue
        files.append(path)
    return files


def pyinstaller_vosk_inputs(pkg_dir: Optional[Path] = None
                            ) -> tuple[list, list, list]:
    """Retorna (datas, binaries, hiddenimports) no formato do Analysis.

    datas/binaries: (src, dest_dir) com dest_dir relativo a _internal,
    sempre começando em 'vosk' para o dirname(__file__) bater.
    """
    root = pkg_dir or vosk_package_dir()
    datas: list[tuple[str, str]] = []
    binaries: list[tuple[str, str]] = []
    hidden = ["vosk", "vosk.vosk_cffi", "cffi", "_cffi_backend"]
    if root is None:
        return datas, binaries, hidden
    for path in iter_vosk_files(root):
        rel_parent = path.parent.relative_to(root)
        dest = "vosk" if rel_parent == Path(".") else str(Path("vosk") / rel_parent)
        dest = dest.replace("\\", "/")
        item = (str(path), dest)
        if path.suffix.lower() in NATIVE_SUFFIXES:
            binaries.append(item)
        else:
            datas.append(item)
    return datas, binaries, hidden


def native_basenames(pkg_dir: Optional[Path] = None) -> list[str]:
    root = pkg_dir or vosk_package_dir()
    if root is None:
        return []
    return sorted(
        p.name for p in iter_vosk_files(root)
        if p.suffix.lower() in NATIVE_SUFFIXES or p.name.lower().startswith("libvosk")
    )


def copy_vosk_into(dest_dir: Path, pkg_dir: Optional[Path] = None) -> list[Path]:
    """Copia o pacote Vosk para dest_dir/vosk (reparo pós-PyInstaller)."""
    import shutil
    root = pkg_dir or vosk_package_dir()
    if root is None:
        return []
    target = dest_dir / "vosk"
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for src in iter_vosk_files(root):
        rel = src.relative_to(root)
        out = target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
        written.append(out)
    return written


def bundle_has_native(internal_dir: Path) -> bool:
    """True se _internal/vosk contém a biblioteca nativa."""
    folder = internal_dir / "vosk"
    if not folder.is_dir():
        return False
    names = {p.name.lower() for p in folder.iterdir() if p.is_file()}
    return any(n.startswith("libvosk") or n == "libvosk.dll" or n == "libvosk.so"
               or n == "libvosk.dyld" for n in names)
