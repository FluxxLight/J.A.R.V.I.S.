# =============================================================================
# J.A.R.V.I.S. — Just A Rather Very Intelligent System
# Fundação + HUB + finalização (Prompt 4)
# Python • 100% local • "IA sem ser IA" (regras, sem LLM, sem nuvem)
# =============================================================================

"""Pacote principal do J.A.R.V.I.S.

A versão do produto vive APENAS aqui. CLI (`--version`), HUB, configurações,
diagnóstico, build e auditoria importam `__version__` — nunca duplicar o
número em string solta.
"""

__version__ = "2.2.0"
__author__ = "J.A.R.V.I.S. Project"
__language__ = "pt-BR"

from jarvis.core.states import SystemState  # noqa: F401
