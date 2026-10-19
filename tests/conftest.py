"""Fixtures compartilhadas: engine isolado em diretório temporário (dry-run)."""

import pytest

from jarvis.actions.system import register_all as register_actions
from jarvis.command_engine.engine import CommandEngine
from jarvis.commands.custom import CustomCommandManager
from jarvis.commands.native import register_all as register_native
from jarvis.commands.registry import CommandRegistry
from jarvis.context.context import ContextManager
from jarvis.core.app import JarvisApp
from jarvis.memory.memory import MemoryManager
from jarvis.settings.settings import SettingsManager
from jarvis.storage import paths
from jarvis.voice.pipeline import VoiceInputPipeline


@pytest.fixture()
def data_dir(tmp_path):
    paths.set_base_dir(tmp_path)
    yield tmp_path
    paths.set_base_dir(None)


@pytest.fixture()
def registry():
    reg = CommandRegistry()
    register_actions(reg)
    register_native(reg)
    return reg


@pytest.fixture()
def engine(registry, data_dir):
    ctx = ContextManager()
    mem = MemoryManager(data_dir / "memory.json")
    return CommandEngine(registry=registry, context=ctx, memory=mem,
                         confirm_dangerous=True, dry_run=True)


@pytest.fixture()
def custom_mgr(registry, data_dir):
    return CustomCommandManager(registry, data_dir / "custom.json")


@pytest.fixture()
def voice(engine):
    return VoiceInputPipeline(engine, wake_word_required=False)


@pytest.fixture()
def app(data_dir):
    application = JarvisApp(data_dir=data_dir, dry_run=True)
    application.start()
    yield application
    application.shutdown()
