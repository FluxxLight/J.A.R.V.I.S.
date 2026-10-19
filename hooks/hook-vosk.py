"""Hook PyInstaller: empacota o diretório nativo do Vosk em _internal/vosk.

Sem isso, vosk.__init__.open_dll() chama os.add_dll_directory(dirname(__file__))
apontando para uma pasta que o one-dir não cria — WinError 2.
"""

from pathlib import Path
import sys

# hookspath aponta para hooks/; a raiz do projeto é o pai
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis.packaging.vosk_bundle import pyinstaller_vosk_inputs, native_basenames, vosk_package_dir

datas, binaries, hiddenimports = pyinstaller_vosk_inputs()
print("hook-vosk: package dir =", vosk_package_dir())
print("hook-vosk: nativos =", native_basenames())
print("hook-vosk: datas =", len(datas), "binaries =", len(binaries))
