"""Configurações: recuperação de ausente/vazia/corrompida/inválida."""

from jarvis.settings.settings import DEFAULTS, SettingsManager


def test_creates_defaults_when_missing(data_dir):
    mgr = SettingsManager(data_dir / "settings.json")
    assert mgr.get("language") == "pt-BR"
    assert (data_dir / "settings.json").exists()


def test_corrupt_file_recovers(data_dir):
    path = data_dir / "settings.json"
    path.write_text("{json inválido!!!", encoding="utf-8")
    mgr = SettingsManager(path)  # não pode crashar
    assert mgr.get("language") == DEFAULTS["language"]
    assert (data_dir / "backup").exists()  # backup do corrompido


def test_empty_file_recovers(data_dir):
    path = data_dir / "settings.json"
    path.write_text("   ", encoding="utf-8")
    mgr = SettingsManager(path)
    assert mgr.get("tts.rate") == DEFAULTS["tts"]["rate"]


def test_invalid_values_sanitized(data_dir):
    path = data_dir / "settings.json"
    path.write_text('{"tts": {"rate": "rapidíssimo", "volume": 99}, "voice": "x"}',
                    encoding="utf-8")
    mgr = SettingsManager(path)
    assert mgr.get("tts.rate") == DEFAULTS["tts"]["rate"]
    assert mgr.get("voice.enabled") is True  # seção refeita


def test_vad_sensitivity_clamped(data_dir):
    mgr = SettingsManager(data_dir / "settings.json")
    mgr.set("voice.vad_sensitivity", 9.0)
    assert mgr.get("voice.vad_sensitivity") == 2.0
    mgr.set("voice.vad_sensitivity", 0.1)
    assert mgr.get("voice.vad_sensitivity") == 0.5


def test_volume_clamped(data_dir):
    mgr = SettingsManager(data_dir / "settings.json")
    mgr.set("tts.volume", 5.0)
    assert mgr.get("tts.volume") == 1.0


def test_get_set_roundtrip(data_dir):
    mgr = SettingsManager(data_dir / "settings.json")
    assert mgr.set("voice.wake_word_required", True) is True
    assert mgr.get("voice.wake_word_required") is True
    fresh = SettingsManager(data_dir / "settings.json")
    assert fresh.get("voice.wake_word_required") is True
