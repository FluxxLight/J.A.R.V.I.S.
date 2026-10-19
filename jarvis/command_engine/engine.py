"""Command Intelligence Engine — interpretação local 100% determinística.

Pipeline:
    texto -> normalização -> confirmação pendente? -> contexto ->
    matching (frases+aliases) -> entidades/parâmetros -> validação ->
    confirmação (se perigoso) -> execução -> feedback -> memória/contexto

TEXTO e VOZ usam este mesmo motor (a voz só transcreve e chama `process`).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from jarvis.command_engine import entities
from jarvis.command_engine import intents as I
from jarvis.command_engine.confirmations import ConfirmationManager, PendingConfirmation
from jarvis.command_engine.matcher import MIN_CONFIDENCE, score_pattern
from jarvis.command_engine.normalizer import normalize
from jarvis.commands.base import ActionContext, Command
from jarvis.commands.registry import CommandRegistry
from jarvis.context.context import ContextManager, Interaction
from jarvis.logger import get_logger
from jarvis.memory.memory import MemoryManager

log = get_logger("engine")


@dataclass
class EngineResult:
    success: bool
    intent: str = I.UNKNOWN
    command_id: str = ""
    action_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    method: str = "none"
    normalized: str = ""
    context_applied: str = ""
    needs_confirmation: bool = False
    confirm_prompt: str = ""
    message: str = ""       # texto para exibir
    speak_text: str = ""    # texto para o TTS falar
    executed: bool = False


class CommandEngine:
    def __init__(self, registry: CommandRegistry,
                 context: Optional[ContextManager] = None,
                 memory: Optional[MemoryManager] = None,
                 confirmations: Optional[ConfirmationManager] = None,
                 confirm_dangerous: bool = True,
                 request_exit: Optional[Callable[[], None]] = None,
                 dry_run: bool = False) -> None:
        self.registry = registry
        self.context = context or ContextManager()
        self.memory = memory  # opcional; None = sem persistência de memória
        self.confirmations = confirmations or ConfirmationManager()
        self.confirm_dangerous = confirm_dangerous
        self._request_exit = request_exit
        self.dry_run = dry_run
        self._lock = threading.RLock()

    def set_request_exit(self, callback: Callable[[], None]) -> None:
        self._request_exit = callback

    # -- API principal -----------------------------------------------------
    def process(self, text: str | None, source: str = "text") -> EngineResult:
        """Processa TEXTO ou TRANSCRIÇÃO DE VOZ. Nunca levanta exceção."""
        with self._lock:
            try:
                return self._process_safe(text, source)
            except Exception as exc:  # última barreira: nunca crashar
                log.exception("Falha inesperada no engine")
                return EngineResult(
                    success=False, message=f"Ocorreu um erro interno: {exc}",
                    speak_text="Desculpe, ocorreu um erro interno.")

    def _process_safe(self, text: str | None, source: str) -> EngineResult:
        raw = (text or "").strip()
        if not raw:
            return EngineResult(success=False, message="Não entendi. Pode repetir?",
                                speak_text="Não entendi. Pode repetir?")
        if len(raw) > 500:
            log.warning("Entrada muito longa (%d chars). Truncando.", len(raw))
            raw = raw[:500]

        normalized = normalize(raw)
        log.info("ENGINE INPUT [%s]: %r -> %r", source, raw, normalized)
        if not normalized:
            return EngineResult(success=False, normalized=normalized,
                                message="Não entendi. Pode repetir?",
                                speak_text="Não entendi. Pode repetir?")

        # 1) Confirmação pendente tem prioridade total
        if self.confirmations.has_pending():
            answer = self.confirmations.resolve(raw)
            if answer is True:
                return self._execute_pending(source, raw)
            if answer is False:
                log.info("Confirmação cancelada pelo usuário.")
                return EngineResult(success=True, intent="CANCEL",
                                    message="Cancelado.", speak_text="Cancelado.")
            pending = self.confirmations.peek()
            assert pending is not None
            return EngineResult(
                success=False, intent=pending.intent, needs_confirmation=True,
                confirm_prompt=pending.prompt, normalized=normalized,
                message=f"{pending.prompt} (diga 'sim' ou 'não')",
                speak_text=pending.prompt)

        # 2) Contexto (pronomes, continuação, repetição)
        context_note = ""
        effective = normalized
        resolution = self.context.resolve(normalized)
        if resolution.applied and resolution.rewritten_text:
            effective = resolution.rewritten_text
            context_note = resolution.note
            log.info("Contexto aplicado (%s): %r", context_note, effective)

        # 3) Matching contra comandos habilitados
        best_cmd: Optional[Command] = None
        best_score = 0.0
        best_method = "none"
        for cmd in self.registry.enabled():
            for pattern in cmd.all_patterns():
                result = score_pattern(normalize(pattern), effective)
                total = result.score + (cmd.priority / 10000.0)  # desempate
                if total > best_score:
                    best_score, best_cmd = total, cmd
                    best_method = result.method

        # 3b) Regra de alta precisão para URLs ("abra o youtube",
        #     "abra o site https://..."): vence matches genéricos fracos,
        #     mas respeita comandos (inclusive personalizados) quase exatos.
        rule_params = entities.detect_url_intent(raw, effective)
        if rule_params:
            url_cmd = self.registry.get("native.open_url")
            if (url_cmd is not None and url_cmd.enabled
                    and (best_cmd is None or best_score < 0.90
                         or best_cmd.intent == I.OPEN_URL)):
                log.info("Regra OPEN_URL aplicada: %r", rule_params)
                best_cmd, best_method = url_cmd, "rule"
                best_score = max(best_score, 0.95)

        if best_cmd is None or best_score < MIN_CONFIDENCE:
            log.info("Sem intenção confiante (score=%.3f).", best_score)
            self._record_context(raw, normalized, I.UNKNOWN, {}, None, False)
            return EngineResult(
                success=False, intent=I.UNKNOWN, score=round(best_score, 4),
                method=best_method, normalized=normalized,
                message=("Não reconheci esse comando. Diga 'ajuda' para ver "
                         "o que posso fazer."),
                speak_text="Não reconheci esse comando.")

        score = round(best_score, 4)
        log.info("INTENT=%s cmd=%s score=%.3f method=%s ctx=%s",
                 best_cmd.intent, best_cmd.id, score, best_method, context_note)

        # 4) Parâmetros/entidades (regra de URL tem precedência)
        params = entities.build_params(best_cmd.intent, raw, effective, best_cmd.params)
        if rule_params and best_cmd.intent == I.OPEN_URL:
            params.update(rule_params)
        log.info("PARAMS=%r", params)

        # 5) Ação registrada?
        action = self.registry.get_action(best_cmd.action_id)
        if action is None:
            log.error("Ação não registrada: %s", best_cmd.action_id)
            return EngineResult(
                success=False, intent=best_cmd.intent, command_id=best_cmd.id,
                score=score, method=best_method, normalized=normalized,
                message="Este comando está com problema interno (ação ausente).",
                speak_text="Este comando está indisponível.")

        # 6) Validação
        error = action.validate(params)
        if error:
            log.warning("Validação falhou: %s", error)
            return EngineResult(
                success=False, intent=best_cmd.intent, command_id=best_cmd.id,
                action_id=action.id, params=params, score=score,
                method=best_method, normalized=normalized,
                message=error, speak_text=error)

        # 7) Confirmação para ações perigosas
        needs_confirm = (
            self.confirm_dangerous
            and (action.requires_confirmation or best_cmd.requires_confirmation
                 or best_cmd.intent in I.DANGEROUS_INTENTS)
        )
        if needs_confirm:
            prompt = getattr(action, "confirm_prompt", "Tem certeza?") or "Tem certeza?"
            self.confirmations.request(PendingConfirmation(
                intent=best_cmd.intent, command_id=best_cmd.id,
                action_id=action.id, params=params, prompt=prompt, source=source))
            log.info("Confirmação solicitada: %s", prompt)
            return EngineResult(
                success=False, intent=best_cmd.intent, command_id=best_cmd.id,
                action_id=action.id, params=params, score=score,
                method=best_method, normalized=normalized,
                context_applied=context_note, needs_confirmation=True,
                confirm_prompt=prompt, message=f"{prompt} (diga 'sim' ou 'não')",
                speak_text=prompt)

        # 8) Execução
        return self._execute(best_cmd, action.id, params, raw, normalized,
                             effective, score, best_method, context_note,
                             source, confirmed=False)

    # -- execução ----------------------------------------------------------
    def _execute_pending(self, source: str, raw: str) -> EngineResult:
        pending = self.confirmations.take()
        if pending is None:  # expirou entre resolve() e take()
            log.warning("Confirmação expirou antes da execução.")
            return EngineResult(success=False, message="A confirmação expirou.",
                                speak_text="A confirmação expirou. Pode repetir?")
        cmd = self.registry.get(pending.command_id)
        log.info("Confirmação aceita: %s", pending.intent)
        return self._execute(cmd, pending.action_id, pending.params, raw,
                             normalize(raw), normalize(raw), 1.0, "confirmed",
                             "", source, confirmed=True)

    def _execute(self, cmd: Optional[Command], action_id: str,
                 params: dict[str, Any], raw: str, normalized: str,
                 effective: str, score: float, method: str,
                 context_note: str, source: str, confirmed: bool) -> EngineResult:
        action = self.registry.get_action(action_id)
        intent = cmd.intent if cmd else I.UNKNOWN
        cmd_id = cmd.id if cmd else ""
        if action is None:
            return EngineResult(success=False, intent=intent, message="Ação ausente.",
                                speak_text="Ação indisponível.")
        ctx = ActionContext(source=source, raw_text=raw, confirmed=confirmed,
                            request_exit=self._request_exit, dry_run=self.dry_run)
        log.info("EXECUTING action=%s params=%r confirmed=%s dry_run=%s",
                 action_id, params, confirmed, self.dry_run)
        try:
            result = action.execute(params, ctx)
        except PermissionError as exc:
            log.exception("Ação sem permissão")
            result = type("R", (), {"success": False,
                                    "message": f"Sem permissão: {exc}",
                                    "speak_text": "Sem permissão para essa ação.",
                                    "data": {}})()
        except FileNotFoundError as exc:
            log.exception("Alvo não encontrado")
            result = type("R", (), {"success": False,
                                    "message": f"Não encontrado: {exc}",
                                    "speak_text": "Não encontrei o programa ou arquivo.",
                                    "data": {}})()
        except Exception as exc:  # noqa: BLE001 - qualquer erro de ação é contido
            log.exception("Ação falhou")
            result = type("R", (), {"success": False,
                                    "message": f"Falha ao executar: {exc}",
                                    "speak_text": "Não consegui executar esse comando.",
                                    "data": {}})()

        app = params.get("app") if isinstance(params.get("app"), str) else None
        url = params.get("url") if isinstance(params.get("url"), str) else None
        self._record_context(raw, effective, intent, params, app, result.success)
        if self.memory is not None:
            try:
                self.memory.record_execution(intent, raw, result.success)
            except Exception:
                log.exception("Falha ao registrar memória (não fatal)")

        log.info("RESULT success=%s msg=%r", result.success, result.message)
        return EngineResult(
            success=result.success, intent=intent, command_id=cmd_id,
            action_id=action_id, params=params, score=score, method=method,
            normalized=normalized, context_applied=context_note,
            message=result.message or "Feito.",
            speak_text=result.speak_text or "Feito.",
            executed=True)

    def _record_context(self, raw: str, effective: str, intent: str,
                        params: dict[str, Any], app: Optional[str],
                        success: bool) -> None:
        try:
            url = params.get("url") if isinstance(params.get("url"), str) else None
            self.context.push(Interaction(
                text=raw, normalized=effective, intent=intent,
                entities=dict(params), app=app, url=url, success=success))
        except Exception:
            log.exception("Falha ao registrar contexto (não fatal)")
