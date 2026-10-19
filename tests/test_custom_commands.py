"""CRUD real de comandos personalizados + execução via engine."""

import pytest

from jarvis.commands.custom import CustomCommandError


def test_create_and_execute(custom_mgr, engine):
    item = custom_mgr.create(
        name="Abrir Discord", phrases=["abra o discord", "inicie o discord"],
        action="open_app", params={"app": "discord"})
    assert item["id"].startswith("custom_")
    r = engine.process("inicie o discord")
    assert r.success is True
    assert r.action_id == "OpenApplication"
    assert r.params.get("app") == "discord"


def test_create_open_url(engine, custom_mgr):
    custom_mgr.create(name="Meu Site", phrases=["abra meu site"],
                      action="open_url", params={"url": "https://example.com"})
    r = engine.process("abra meu site")
    assert r.success is True
    assert r.params.get("url") == "https://example.com"


def test_invalid_url_rejected(custom_mgr):
    with pytest.raises(CustomCommandError):
        custom_mgr.create(name="X", phrases=["x comando"], action="open_url",
                          params={"url": "ht!tp: invalida"})


def test_update_and_delete(custom_mgr, engine):
    item = custom_mgr.create(name="Falar", phrases=["fale oi"],
                             action="speak", params={"text": "Oi!"})
    custom_mgr.update(item["id"], phrases=["diga oi"])
    assert engine.process("diga oi").success is True
    assert custom_mgr.delete(item["id"]) is True
    assert custom_mgr.get(item["id"]) is None


def test_disable_enable(custom_mgr, engine):
    item = custom_mgr.create(name="Tmp", phrases=["comando temporario xyz"],
                             action="speak", params={"text": "ok"})
    assert engine.process("comando temporario xyz").success is True
    assert custom_mgr.set_enabled(item["id"], False) is True
    assert engine.process("comando temporario xyz").success is False
    assert custom_mgr.set_enabled(item["id"], True) is True
    assert engine.process("comando temporario xyz").success is True


def test_persists_to_disk(custom_mgr, data_dir):
    item = custom_mgr.create(name="Persist", phrases=["persista isso"],
                             action="speak", params={"text": "ok"})
    fresh = type(custom_mgr)(custom_mgr._registry, data_dir / "custom.json")
    assert fresh.get(item["id"]) is not None
