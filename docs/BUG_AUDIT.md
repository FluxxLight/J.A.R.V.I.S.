# BUG AUDIT — J.A.R.V.I.S. 2.0.0 (PROMPT 3.4)

> Caça sistemática a bugs **antes** do build final. Três ciclos, focos
> diferentes, 74 verificações executáveis. Só há "PRONTO" porque cada ciclo
> terminou em **0 falhas reproduzíveis** — e o único bug real encontrado foi
> corrigido, testado e eternizado como teste de regressão.

Scripts reproduzíveis em `docs/audit/` (`cycle1_core_stress.py`,
`cycle2_hub_qt.py`, `cycle3_races_edges.py`). Foram escritos como sondas de
auditoria (não entram no `pytest`): para rodar, use o mesmo ambiente dos
testes Qt — `QT_QPA_PLATFORM=offscreen`, `PYTHONPATH=<repo>` e, no sandbox
Linux sem libGL do sistema, `LD_LIBRARY_PATH=<stubs-qt>`.

**Estado final: 74/74 PASS. Nenhum crash reproduzível. Nenhum placeholder.
Nenhum bug crítico/alto sem tratamento.**

---

## Ciclo 1 — núcleo sob estresse (34/34 ✅)

Foco: engine, comandos personalizados, performance, vazamentos,
resiliência de storage, voz extrema, fuzz.

| # | Verificação | Resultado |
|---|-------------|-----------|
| 1–12 | CRUD de 30 comandos personalizados (criar/usar texto+voz, renomear, desabilitar, deletar, persistência após restart) | 12/12 ✅ |
| 13–15 | 200 comandos cronometrados (p50/p95/p200), sem degradação | p50 ≈ 1ms, p200 ≈ 13ms ✅ |
| 16–17 | Threads e RSS estáveis após carga (2→2 threads, RSS plano) | ✅ |
| 18–22 | Sabotagem de storage (JSON corrompido, permissões, disco) — 20/20 recuperações honestas | ✅ |
| 23–26 | Voz extrema (transcrições vazias/gigantes/unicode, TTS longo, fila sob carga) — 0 crashes | ✅ |
| 27–34 | Fuzz de ~11.000 operações (comandos aleatórios, parâmetros absurdos, concorrência leve) — 0 exceções não tratadas | ✅ |

**Bug real encontrado e corrigido (único do ciclo):**
corrida assíncrona TTS↔pipeline — com fala ainda ativa e novo comando
chegando, o app tentava `SPEAKING → EXECUTING` e o `StateManager` recusava,
registrando "Transição inválida" e deixando o estado inconsistente.
Correção em `jarvis/core/states.py`: `SPEAKING` agora pode ceder para
`PROCESSING`, `EXECUTING` e `LISTENING` (falar nunca bloqueia trabalho novo).
Regressão: `tests/test_regression.py::test_audit_regression_speaking_may_yield_to_work`.

**Falsos positivos da própria auditoria (corrigidos no script, não no produto):**
frases sobrepostas (`numero 1` casa dentro de `numero 11` — asserção ajustada
para `command_id !=`), `resource.get_ru_maxrss` inexistente (usar
`getrusage`), e idempotência (scripts agora limpam o `data_dir`).

---

## Ciclo 2 — HUB Qt sob estresse (18/18 ✅)

Foco: janela principal, temas, fullscreen, workers, diálogos, intro,
núcleo animado, ciclo de vida, resoluções, storm de eventos.

| # | Verificação | Resultado |
|---|-------------|-----------|
| 1–2 | Startup do core < 5s; abertura do HUB < 5s | 0.00s / 0.53s ✅ |
| 3 | 30 combinações tema×estado sem erro de pintura | 0 erros ✅ |
| 4 | F11 (fullscreen on/off) × 20 | ✅ |
| 5–6 | 30 comandos via workers do HUB; badge final volta a EM ESPERA | ✅ |
| 7 | Diálogos (settings/comandos) abrir/fechar × 10 | ✅ |
| 8 | Intro com skip × 5 (encerra limpo, sem travar) | ✅ |
| 9–10 | Núcleo 5 temas × 7 estados; pintura ≤ 33ms (meta 30fps+) | 5.1ms ✅ |
| 11 | 5 ciclos criar→mostrar→fechar→destruir HUB (sem "Signal source has been deleted") | ✅ |
| 12–13 | Diálogo de comando: 10 válidos aceitos, 10 inválidos bloqueados | ✅ |
| 14 | Autostart liga/desliga × 20 (idempotente; no-op honesto fora do Windows) | ✅ |
| 15 | Diagnóstico × 10 (saída estável) | ✅ |
| 16 | Render em 4 resoluções (800×600 → 1920×1080, inclui 1280×720 e 1366×768) | ✅ |
| 17 | HUB abre com `settings.json` corrompido (cai para padrão, não crasha) | ✅ |
| 18 | Storm de 500 eventos PROCESSANDO (coalescência, sem travar UI) | ✅ |

Nenhum bug de produto. (Durante o desenvolvimento deste ciclo, o trabalho
de bisection já havia isolado a regressão do PySide6 6.12.0 — crash por
refcount após centenas de operações Qt cumulativas — e pinado
`PySide6>=6.6,<6.12`. Ver sessão "Dependências" do README.)

---

## Ciclo 3 — corridas, interrupções e casos impossíveis (22/22 ✅)

Foco: concorrência real, interrupção no meio do trabalho, entradas
absurdas, backends ausentes, entry points, invariantes de ciclo de vida.

| # | Verificação | Resultado |
|---|-------------|-----------|
| 1 | Fechar o HUB durante worker ativo (sem travar; fecha em 0.51s) | ✅ |
| 2 | Handlers do EventBus voltam ao baseline após destruir HUB (6→12→6, sem vazamento) | ✅ |
| 3 | WAV de SFX ausente → `play()` retorna `False`, sem crash | ✅ |
| 4 | Troca de backend TTS em runtime + fala | ✅ |
| 5 | `settings.set` concorrente (10 threads × 20) — JSON final válido | ✅ |
| 6 | `memory.record_execution` concorrente (10 × 50) — 0 erros | ✅ |
| 7 | `engine.process` concorrente (10 × 20 comandos seguros) — 0 erros | ✅ |
| 8 | HUB: texto vazio / só espaços / 10KB — processa e libera `_busy` | ✅ |
| 9 | 100 transcrições alternando com/sem wake word | ✅ |
| 10 | Contexto expira após TTL (pronome sem contexto não resolve) | ✅ |
| 11 | Comando nativo removido → UNKNOWN honesto; ação ausente → erro honesto ("ação ausente") | ✅ |
| 12 | `data_dir` com espaço e unicode (`/tmp/audit dir çãõ`) | ✅ |
| 13–16 | Entry points: `--version` (exit 0, "2.0.0"), `--exec` ok (0), `--exec` desconhecido (1), `--test-voice` (0 + OPEN_BROWSER) | ✅ |
| 17 | `SpeechQueue`: shutdown duplo idempotente; `speak` pós-shutdown = `False` | ✅ |
| 18 | Microfone/reconhecedor indisponíveis (sem sounddevice/Vosk): `None`/transcrição vazia, sem crash | ✅ |
| 19 | `show_and_focus` × 10 + troca de QSS × 20 | ✅ |
| 20 | `make_icon` em 6 tamanhos + diálogo de comando vazio bloqueia salvar | ✅ |
| 21 | Intro: `start()` duplo + `skip()` sem `start()` — encerra limpo | ✅ |
| 22 | (implícito em todos) 0 tracebacks não tratados no stderr filtrado | ✅ |

**Falso positivo da própria auditoria:** a expectativa inicial procurava a
palavra "indispon" na mensagem de ação ausente; o produto responde, com
honestidade, `"Este comando está com problema interno (ação ausente)."`
(`success=False` + log `ERROR`). Verificado à mão e corrigida a expectativa.

---

## Bugs conhecidos que NÃO são bugs do produto

1. **PySide6 6.12.0** — regressão de refcount/GC upstream ("none_dealloc",
   crash fatal após centenas de operações Qt cumulativas; reproduz com
   `QLabel.setText` × 3000 puro). Mitigação: `requirements-ui.txt` pinado
   em `PySide6>=6.6,<6.12`; validado em 6.7.2 com stress (60 pinturas
   pesadas do núcleo + setText × 3000, 0 crashes).
2. **Sandbox sem libGL/áudio/Vosk/display/Windows** — os testes Qt rodam em
   `offscreen` + raster com stubs de versão; voz real, autostart de
   registro e `.exe` só são exercitáveis no Windows. O `build.py` detecta
   isso e roda em "modo verificação" fora do Windows.

---

## Regra de regressão (vale para todo PR futuro)

1. **Todo bug encontrado por auditoria, review ou usuário vira teste.**
   Sem exceção: corrigir sem teste de regressão em `tests/` (unitário) ou
   `docs/audit/` (stress/ciclo de vida) não conta como corrigido.
2. **Suíte sempre verde antes de commit:** `pytest` (hoje 178 testes) com
   **0 falhas e 0 warnings**; `python -m compileall` limpo.
3. **Nenhum upgrade de PySide6 além de 6.11.x** sem rodar o stress
   (`setText` × 3000 + 60 pinturas do núcleo) em `docs/audit/cycle2_hub_qt.py`.
4. **Toda mudança no `StateManager`** roda `test_regression.py` +
   ciclo 1 (a máquina de estados é o coração do feedback real).
5. **Toda mudança visual no HUB** exige re-shot offscreen dos 5 temas +
   `intro` antes do commit (receita na seção "HUB / Interface" do README).
