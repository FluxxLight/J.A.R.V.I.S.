"""SFX sintetizados: válidos, curtos, determinísticos (sem Qt)."""

import wave

from jarvis.ui.hub import sfx
from jarvis.ui.hub.sfx import SOUNDS, to_wav_bytes


def test_all_sounds_generate():
    for name, maker in SOUNDS.items():
        samples = maker()
        assert len(samples) > 100, name
        assert all(-1.0 <= s <= 1.0 for s in samples), name


def test_deterministic():
    assert sfx.make_boot() == sfx.make_boot()
    assert sfx.make_ready() == sfx.make_ready()


def test_wav_bytes_valid(tmp_path):
    for name, maker in SOUNDS.items():
        data = to_wav_bytes(maker())
        assert data[:4] == b"RIFF", name
        path = tmp_path / f"{name}.wav"
        path.write_bytes(data)
        with wave.open(str(path), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == sfx.SAMPLE_RATE
            seconds = wav.getnframes() / wav.getframerate()
            assert 0.03 <= seconds <= 1.5, (name, seconds)


def test_committed_assets_exist_and_match():
    for name in SOUNDS:
        asset = sfx.ASSETS_DIR / f"{name}.wav"
        assert asset.exists(), f"asset ausente: {asset}"
        assert asset.stat().st_size > 1000


def test_sfx_player_null_backend_safe():
    from jarvis.ui.hub.audio import SfxPlayer, sfx_path
    player = SfxPlayer(enabled=True)
    assert player.play("nope") is False  # nome inválido
    player.set_enabled(False)
    assert player.play("boot") is False  # desabilitado
    player.set_enabled(True)
    # em qualquer backend, nunca levanta
    player.play("boot")
    player.stop_all()
    assert sfx_path("boot") is not None
    assert sfx_path("inexistente") is None
