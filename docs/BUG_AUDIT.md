# BUG AUDIT — J.A.R.V.I.S. 2.2.0

> Caça sistemática a bugs **antes** de declarar o produto pronto. Quatro
> ciclos, focos diferentes, scripts em `docs/audit/`. Só há "PRONTO" porque
> cada ciclo terminou em **0 falhas reproduzíveis** — e cada bug real foi
> corrigido, testado e eternizado como regressão.

Scripts: `cycle1_core_stress.py`, `cycle2_hub_qt.py`, `cycle3_races_edges.py`,
`cycle4_final.py`. Não entram no `pytest`: rode com o mesmo ambiente dos
testes Qt — `QT_QPA_PLATFORM=offscreen`, `PYTHONPATH=<repo>` e, no sandbox
Linux sem libGL, `LD_LIBRARY_PATH=<stubs-qt>`.

**Estado final: 96/96 PASS (34+18+22+22). Nenhum crash reproduzível.
Nenhum placeholder. Nenhum bug crítico/alto sem tratamento.**

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
| 15 | Diagnóstico × 10 (saída estável, 10 itens incluindo Versão) | ✅ |
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
| 13–16 | Entry points: `--version` (exit 0, `jarvis.__version__`), `--exec` ok (0), `--exec` desconhecido (1), `--test-voice` (0 + OPEN_BROWSER) | ✅ |
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

## Ciclo 4 — finalização (PROMPT 4) (22/22 ✅)

Foco: versão única, auditoria de rede, segurança (texto ≠ shell), layout
DPI/resolução, persistência, CLI real, SFX/frozen paths, autostart.

Script: `docs/audit/cycle4_final.py`.

| # | Verificação | Resultado |
|---|-------------|-----------|
| 1–2 | Versão semver, declarada uma vez em `jarvis.__version__` | 2.1.0 ✅ |
| 3–5 | `--version`, `python -m jarvis --version`, exit 1 em comando desconhecido | ✅ |
| 6 | AST: zero imports de cliente HTTP/LLM/telemetria | ✅ |
| 7–9 | Texto hostil = UNKNOWN; wake word preserva `rm -rf /` e não executa | ✅ |
| 10 | Pares texto==voz do prompt 4 (navegador, hora, data, bloco de notas) | ✅ |
| 11–12 | Tema e `intro.enabled` persistem após restart | ✅ |
| 13–14 | Layout 5 resoluções (800×600→2560×1440); mínimo ≤ 800×560 | ✅ |
| 15–16 | Checkboxes de intro sincronizados nos dois sentidos | ✅ |
| 17 | Animações aplicam a quente no núcleo | ✅ |
| 18–19 | CLI `--fullscreen` / `--minimized` existem | ✅ |
| 20 | 6 SFX locais presentes em disco | ✅ |
| 21–22 | Autostart aponta para `main.py --hub` existente | ✅ |

### Bugs encontrados neste ciclo

**BUG-004**
- **BUG:** HUB com `setMinimumSize(1100, 680)` e colunas fixas 300+320 px.
- **CAUSA:** layout pensado só para 1440×860 @ 100% DPI.
- **SEVERIDADE:** ALTO (1280×720 @ 125% e 1366×768 @ 150% ficam abaixo do mínimo).
- **REPRODUÇÃO:** `hub.setMinimumSize` + `resize(800, 600)` — Qt recusava encolher.
- **CORREÇÃO:** mínimo 800×560; `_adapt_layout` reduz colunas por faixa de largura.
- **REGRESSÃO:** `tests/test_hub_qt.py::test_hub_resolutions` (inclui 800×600 e 2560×1440).
- **STATUS:** CORRIGIDO.

**BUG-005**
- **BUG:** checkbox "Mostrar intro" em Aparência não sincronizava com o da aba Inicialização.
- **CAUSA:** só o da Inicialização empurrava o outro; o inverso só persistia.
- **SEVERIDADE:** BAIXO.
- **REPRODUÇÃO:** abrir Config → desmarcar em Aparência → aba Inicialização ainda marcada.
- **CORREÇÃO:** `_on_intro_changed` é a única fonte, atualiza os dois sem loop de sinais.
- **REGRESSÃO:** `tests/test_hub_qt.py::test_settings_intro_checkboxes_stay_in_sync`.
- **STATUS:** CORRIGIDO.

**BUG-006**
- **BUG:** `python -m jarvis --exec "desconhecido"` devolvia exit 0.
- **CAUSA:** `jarvis/__main__.py` chamava `main()` sem `sys.exit`.
- **SEVERIDADE:** MÉDIO (scripts/CI não detectavam falha).
- **REPRODUÇÃO:** `python -m jarvis --cli --exec "xyzzy"`; `echo %ERRORLEVEL%`.
- **CORREÇÃO:** `sys.exit(main())`.
- **REGRESSÃO:** `tests/test_final.py::test_module_entry_propagates_exit_code`.
- **STATUS:** CORRIGIDO.

**BUG-007**
- **BUG:** README documentava `--fullscreen`/`--minimized` e `JARVIS.exe` / `BUILD_INFO.txt` que não existiam; bloco de instalação com `\n` literal.
- **CAUSA:** edição falha + spec (`J.A.R.V.I.S.exe`) divergente do texto.
- **SEVERIDADE:** MÉDIO (documentação mentirosa).
- **REPRODUÇÃO:** `python main.py --help` não listava as flags; `build.py` não gravava `BUILD_INFO.txt`.
- **CORREÇÃO:** flags reais (não persistem), `BUILD_INFO.txt` gerado, README alinhado ao spec.
- **REGRESSÃO:** `tests/test_final.py::test_cli_exposes_fullscreen_and_minimized`.
- **STATUS:** CORRIGIDO.

**BUG-008**
- **BUG:** `"mostre a hora"` / `"mostre a data"` (exemplos do prompt) não casavam GET_TIME/GET_DATE.
- **CAUSA:** aliases nativos cobriam "que horas são" / "me diga as horas", não "mostre".
- **SEVERIDADE:** MÉDIO (frase natural do usuário falhava).
- **REPRODUÇÃO:** `python main.py --exec "mostre a hora"` → UNKNOWN.
- **CORREÇÃO:** aliases em `jarvis/commands/native.py`.
- **REGRESSÃO:** `tests/test_engine.py` + `tests/test_final.py::test_prompt_examples_text_and_voice`.
- **STATUS:** CORRIGIDO.

**BUG-013**
- **BUG:** `J.A.R.V.I.S.exe` crasha no startup com `FileNotFoundError` em `os.add_dll_directory(...\_internal\vosk)`.
- **CAUSA:** `vosk/__init__.py:open_dll()` exige a pasta física `dirname(__file__)` com `libvosk.dll`. O spec só punha `vosk` em `hiddenimports` — o .py ia para o PYZ e **nenhuma** DLL/pasta `_internal/vosk` era criada. `FileNotFoundError` não é `ImportError`, então `create_recognizer` não recuperava e o HUB nem abria.
- **SEVERIDADE:** CRÍTICO.
- **REPRODUÇÃO:** build no Windows com vosk instalado → abrir `dist\JARVIS\J.A.R.V.I.S.exe`.
- **CORREÇÃO:** `jarvis/packaging/vosk_bundle.py` copia o pacote inteiro para `_internal/vosk/`; `hooks/hook-vosk.py` + `jarvis.spec`; `build.py` verifica/repara e **falha o build** se o nativo faltar; `create_recognizer` trata `OSError` para o HUB sobreviver a bundle incompleto.
- **REGRESSÃO:** `tests/test_vosk_bundle.py`.
- **STATUS:** CORRIGIDO (empacotamento). Execução do EXE: REQUER VALIDAÇÃO NO WINDOWS.

**BUG-011**
- **BUG:** captura de microfone sempre vazia no Windows com `sounddevice`.
- **CAUSA:** `RawInputStream.read()` devolve `(data, overflowed)`; o código fazia `bytes(chunk)` no tuple.
- **SEVERIDADE:** CRÍTICO (voz real inutilizável).
- **REPRODUÇÃO:** `listen_once` com sounddevice instalado — transcrição sempre `""`.
- **CORREÇÃO:** `unpack_pcm()` em `jarvis/voice/vad.py`; captura em `jarvis/voice/capture.py`.
- **REGRESSÃO:** `tests/test_vad.py::test_unpack_pcm_tuple_from_sounddevice`.
- **STATUS:** CORRIGIDO.

**BUG-012**
- **BUG:** a frase era cortada no primeiro `AcceptWaveform` do Vosk (antes do usuário terminar).
- **CAUSA:** `listen_once` retornava imediatamente ao primeiro resultado parcial-final do Vosk, sem VAD de fim de fala.
- **SEVERIDADE:** ALTO.
- **REPRODUÇÃO:** falar "J.A.R.V.I.S., abra o navegador" pausando no meio — só "jarvis" ou "abra" chegava.
- **CORREÇÃO:** VAD por energia (calibração + silêncio ~480 ms + mínimo de fala) acumula segmentos até o fim.
- **REGRESSÃO:** `tests/test_vad.py` (fala/silêncio/mínimo) + `capture_utterance` com microfone falso.
- **STATUS:** CORRIGIDO.

**BUG-010**
- **BUG:** `READY → SPEAKING` rejeitado; o HUB não mostrava estado de fala.
- **CAUSA:** TTS é assíncrono — `handle_text` já passou por READY (e às vezes ainda não chegou em IDLE) quando `_on_speech_start` dispara.
- **SEVERIDADE:** MÉDIO (log de transição inválida + estado visual errado).
- **REPRODUÇÃO:** `python main.py --exec "mostre a hora"` com TTS rápido; log `READY -> SPEAKING`.
- **CORREÇÃO:** `READY` passa a permitir `SPEAKING` (simétrico a `IDLE`).
- **REGRESSÃO:** `tests/test_regression.py::test_audit_regression_ready_may_yield_to_speaking`.
- **STATUS:** CORRIGIDO.

**BUG-009**
- **BUG:** animações/FPS das configurações só aplicavam ao fechar o diálogo.
- **CAUSA:** persistiam em `settings.json` mas o núcleo só era atualizado em `_apply_runtime_settings` no `accept`.
- **SEVERIDADE:** BAIXO.
- **REPRODUÇÃO:** desmarcar "Animações" e observar o núcleo ainda pulsar até Fechar.
- **CORREÇÃO:** `_on_anim_changed` / `_on_fps_changed` chamam o núcleo imediatamente.
- **REGRESSÃO:** ciclo 4 (`animações aplicam a quente`).
- **STATUS:** CORRIGIDO.

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
3. **EXE windowed (`console=False`)** — `--version` no EXE Windows pode não
   imprimir stdout; o critério do smoke test é o código de saída. Esperado
   para um app desktop sem console.

---

## Regra de regressão (vale para todo PR futuro)

1. **Todo bug encontrado por auditoria, review ou usuário vira teste.**
   Sem exceção: corrigir sem teste de regressão em `tests/` (unitário) ou
   `docs/audit/` (stress/ciclo de vida) não conta como corrigido.
2. **Suíte sempre verde antes de commit:** `pytest` com **0 falhas e 0
   warnings**; `python -m compileall` limpo.
3. **Nenhum upgrade de PySide6 além de 6.11.x** sem rodar o stress
   (`setText` × 3000 + 60 pinturas do núcleo) em `docs/audit/cycle2_hub_qt.py`.
4. **Toda mudança no `StateManager`** roda `test_regression.py` +
   ciclo 1 (a máquina de estados é o coração do feedback real).
5. **Toda mudança visual no HUB** exige re-shot offscreen dos 5 temas +
   `intro` antes do commit (receita na seção "HUB" do README).
6. **A versão muda em um único lugar:** `jarvis/__init__.py` `__version__`.
   Qualquer string solta `"X.Y.Z"` em testes/auditoria deve importar essa constante.
