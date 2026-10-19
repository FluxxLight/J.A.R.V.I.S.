# J.A.R.V.I.S. — Just A Rather Very Intelligent System

Assistente desktop para **Windows**, escrito em **Python**, **100% local e offline**:
nenhum LLM, nenhuma API de IA, nenhum áudio ou comando sai do computador.
A "inteligência" é determinística: regras, matching, aliases, intenções,
parâmetros, contexto e memória local — *"IA sem ser IA"*.

> Versão **2.2.0 — Refinamento**. HUB profissional, VAD local (fim de fala,
> silêncio, ruído), intro cinematográfica, 5 temas, configurações reais,
> voz local, Command Engine único, build `.exe` e auditoria. O HUB consome
> os mesmos estados/serviços da fundação 1.2 — nenhum sistema duplicado.

A versão do produto vive em um único lugar: `jarvis.__version__`
(CLI `--version`, HUB, configurações, diagnóstico e `BUILD_INFO.txt`).

---

## 1. Arquitetura

```
TEXTO ──┐
        ├─► NORMALIZAÇÃO ─► COMMAND ENGINE ─► INTENÇÃO ─► AÇÃO ─► RESULTADO ─► TTS
VOZ ────┘
  (microfone → reconhecimento local → transcrição → wake word)
```

Texto e voz usam o **mesmo** `CommandEngine` (`jarvis/command_engine/engine.py`).
A voz só transcreve localmente, trata a wake word e chama `process_command()` —
não existe interpretação paralela.

### Módulos (`jarvis/`)

| Pacote | Responsabilidade |
|---|---|
| `core/` | `JarvisApp` (orquestrador), `StateMachine`, `EventBus`, `process_command` unificado |
| `command_engine/` | Normalização, matching, entidades, confirmações, `CommandEngine` |
| `commands/` | Tipos base, `CommandRegistry`, comandos nativos, comandos personalizados (CRUD) |
| `actions/` | Ações centrais reutilizáveis (único lugar com efeito no sistema) |
| `context/` | Janela conversacional: pronomes, continuação, repetição |
| `memory/` | Preferências, fatos, estatísticas, histórico (local) |
| `voice/` | Wake word, pipeline voz→engine, microfone, reconhecedor, TTS, fila de fala |
| `settings/` | `settings.json` com validação e auto-recuperação |
| `storage/` | Caminhos de dados + JSON atômico com backup de corrompidos |
| `system/` | Launcher (apps/URLs/pastas) e operações Windows via `ctypes` |
| `logger/` | Logging em arquivo rotativo + console, com trilha de voz |
| `utils/` | Texto e plataforma (sem dependências) |
| `ui/` | CLI/REPL, GUI mínima (fallback) e HUB (`ui/hub/`: temas, núcleo, intro, SFX, settings, diagnósticos, single-instance, autostart) |

### Estados reais

`STARTING → READY → IDLE → LISTENING → PROCESSING → EXECUTING → SPEAKING → READY`,
com `ERROR → READY` e `SHUTDOWN`.

Emitidos via `EventBus` para o HUB; transições inválidas são rejeitadas e
registradas — o sistema nunca fica preso em `LISTENING`/`PROCESSING`/`EXECUTING`.

---

## 2. Instalação

**Requisitos:** Python 3.10+ no Windows (desenvolvido/testado também em Linux).

```bat
REM núcleo (só stdlib + pytest p/ testes):
pip install -r requirements.txt

REM voz local (opcional, 100% offline após instalado):
pip install -r requirements-voice.txt

REM HUB / interface gráfica:
pip install -r requirements-ui.txt
```

**Dependências (produção, mínimas):** núcleo = stdlib; voz = Vosk +
sounddevice + pyttsx3; UI = PySide6 (`>=6.6,<6.12` — a série 6.12 tem
regressão de refcount/GC upstream que crasha após centenas de operações Qt;
validado em 6.7.2 com stress. Ver `docs/BUG_AUDIT.md`).

Não há `requests`, `httpx`, OpenAI, nem qualquer cliente HTTP no pacote
`jarvis/`. A única "rede" possível é o usuário pedir para abrir uma URL no
navegador (`webbrowser.open`) — o J.A.R.V.I.S. em si não faz requisições.

### Modelo de voz (reconhecimento offline)

1. Baixe um modelo Vosk pt-BR (ex.: `vosk-model-small-pt-0.3`) em
   https://alphacephei.com/vosk/models
2. Extraia para `%APPDATA%\JARVIS\models\vosk\` (ou configure
   `voice.model_path` no `settings.json`).
3. Sem modelo/Vosk, o app continua funcionando em modo texto + voz simulada,
   com aviso claro do motivo — nunca crasha.

---

## 3. Como executar

```bat
run.bat                     REM abre o HUB (com Qt+display) ou cai p/ console
run.bat --cli               REM força console interativo
run.bat --gui               REM janela mínima tkinter (fallback sem Qt)
run.bat --hub               REM força o HUB
run.bat --no-intro          REM HUB sem intro
run.bat --fullscreen        REM HUB em tela cheia (não persiste)
run.bat --minimized         REM HUB minimizado (não persiste)

python main.py --exec "que horas são?"
python main.py --test-voice "J.A.R.V.I.S., abra o navegador."
python main.py --list-mics
python main.py --list-voices
python main.py --dry-run    REM simula ações sem executar (seguro)
```

`--fullscreen` e `--minimized` valem só para a sessão (não gravados em
`settings.json`). A persistência fica nas configurações do HUB.

Comandos do console: `:ouvir` (captura 1 fala), `:voz <texto>` (simula
transcrição), `:mics`, `:vozes`, `:estado`, `:ajuda`, `:sair`.

---

## 4. Como testar

```bat
python -m pytest tests/ -q
```

A suíte cobre a base 1.2 (normalização, matching, wake word — inclui o caso
crítico "comando após a wake word é preservado" — engine, aliases, contexto,
memória, confirmações, customs, storage, settings, estados, pipeline de voz
simulada, erros de voz, regressão texto==voz) + HUB (temas, timeline da intro,
SFX, autostart, single-instance, diagnósticos, integração Qt offscreen) +
fechar-aplicativo end-to-end + regressão da auditoria (`SPEAKING` cedendo a
trabalho novo) + finalização 2.1.0 (versão única, rede, segurança, CLI, layout).

Testes Qt rodam em `offscreen` (sem display): no Linux, exporte
`QT_QPA_PLATFORM=offscreen` (e `LD_LIBRARY_PATH` p/ stubs Qt se o sistema
não tiver libGL — detalhe de sandbox, nunca distribuído).

Auditorias de estresse/ciclo de vida: `docs/audit/` + `docs/BUG_AUDIT.md`
(4 ciclos, verificações executáveis).

```bat
python docs/audit/cycle1_core_stress.py
python docs/audit/cycle2_hub_qt.py
python docs/audit/cycle3_races_edges.py
python docs/audit/cycle4_final.py
```

---

## 5. Comandos nativos

Abrir navegador, calculadora, bloco de notas, explorador, configurações,
Discord, sites/URLs (`"abra o youtube"`, `"abra o site https://..."`),
horas (`"que horas são?"`, `"mostre a hora"`), data (`"mostre a data"`),
minimizar/maximizar/tela-cheia, bloquear, **fechar aplicativo**
(`"feche o discord"`, `"feche ele"` com contexto), **reiniciar**,
**desligar** e **fechar o J.A.R.V.I.S.** (os três últimos exigem "sim"/"não"),
além de `ajuda`.

Entrada do usuário **nunca** é executada como shell: só ações registradas.
Tentativas do tipo `rm -rf /`, `powershell -enc …` ou `curl http://…`
retornam `UNKNOWN` e não executam nada.

### Comandos personalizados (pela UI do HUB ou via código)

```python
from jarvis.core.app import JarvisApp
app = JarvisApp(); app.start()
app.custom_commands.create(
    name="Abrir Discord",
    phrases=["abra o discord", "inicie o discord"],
    action="open_app", params={"app": "discord"})
app.handle_text("inicie o discord")
app.shutdown()
```

Ações de custom: `open_app {app, path?}`, `open_url {url}`,
`open_folder {path}`, `speak {text}`. CRUD completo: `create/update/delete/
set_enabled/list/get`, persistido em `custom_commands.json`.
No HUB: botão **Comandos** → Nativos (somente leitura) + Personalizados
(criar/editar/habilitar/excluir com validação real).

---

## 6. Voz local

- **Reconhecimento:** Vosk offline (`jarvis/voice/recognizer.py`).
  Modelo ausente/biblioteca ausente → motivo claro, modo texto preservado.
- **Captura / VAD:** energia RMS local (`jarvis/voice/vad.py`). Calibra o
  ruído ambiente a cada escuta, diferencia silêncio/ruído/fala/clipping,
  encerra após ~480 ms de silêncio e **não** corta no primeiro `AcceptWaveform`
  do Vosk. Timeout configurável (`voice.listen_timeout`). Sem webrtc/cloud.
- **Wake word:** `jarvis`, `J.A.R.V.I.S.`, com/sem pontuação, início ou meio
  da frase — o comando restante **nunca** é descartado
  (`jarvis/voice/wakeword.py`). Exigibilidade via `voice.wake_word_required`.
- **TTS:** pyttsx3 (SAPI5/Vozes do Windows); lista somente vozes reais;
  sem pyttsx3 → modo texto silencioso. Fila com 1 worker: sem sobreposição,
  com interrupção (`interrupt=True`) e liberação total no shutdown.
- **Debug:** ative o nível DEBUG e cada fala gera a trilha
  `[VOICE RAW] → [RESULT]` no log (`<dados>/logs/jarvis.log`).

---

## 7. Onde ficam os dados locais

| Dado | Local (Windows) |
|---|---|
| Tudo | `%APPDATA%\JARVIS\` |
| Configurações | `settings.json` (auto-recupera se corrompido; backup em `backup\`) |
| Comandos personalizados | `custom_commands.json` |
| Memória | `memory.json` |
| Modelos de voz | `models\vosk\` |
| Logs | `logs\jarvis.log` (rotação 1 MB × 5) |

Override (testes/dev): `python main.py --data-dir ./jarvis_data`.

---

## 8. Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| "Reconhecimento indisponível" | sem Vosk/modelo | `pip install -r requirements-voice.txt` + modelo em `models\vosk\` |
| Nenhum microfone | sem `sounddevice` / sem dispositivo | instalar dep; `:mics` mostra detalhe |
| Não fala | sem pyttsx3 / `tts.enabled=false` | instalar dep; `:vozes` lista vozes reais |
| "Não reconheci" | frase fora dos padrões | diga `ajuda`; veja score no log |
| Ação perigosa não executa | aguardando confirmação | responda `sim` ou `não` (expira em 60 s) |
| `settings.json` corrompido | edição manual/queda | automático: restaura padrão + backup em `backup\` |
| HUB não abre, cai no console | sem PySide6/display | `pip install -r requirements-ui.txt` |
| Crash Qt após minutos de uso | PySide6 6.12 (regressão upstream) | pinar `PySide6>=6.6,<6.12` (ver `docs/BUG_AUDIT.md`) |
| Elementos apertados em tela pequena | DPI alto + resolução baixa | o HUB reduz colunas abaixo de 1280 px; mínimo 800×560 |
| Segunda janela não abre | single instance | a instância existente é focada — é o comportamento correto |
| Autostart não liga no Windows | EXE movido após ativar | desative e ative de novo nas configurações (grava o caminho atual) |
| Build no Linux não gera EXE | PyInstaller Windows-only neste projeto | `build.py` roda em modo verificação; use `build.bat` no Windows |

Logs detalhados sempre em `<dados>\logs\jarvis.log`.

---

## 9. HUB — central de comando

- **Núcleo animado** no centro: cada um dos 8 estados tem comportamento
  visual próprio (pulso, órbitas, partículas, véu de erro), sempre refletindo
  o `StateMachine` real — nunca animação decorativa desconectada.
- **Feedback real de comando:** a trilha `COMANDO → PROCESSANDO →
  EXECUTANDO → RESULTADO` espelha o `EngineResult` verdadeiro
  (intenção, confiança, método, duração, mensagem).
- **HUD com propósito:** relógio/data, estado atual, último comando +
  confiança, contadores da sessão, atalhos. Nada é enfeite.
- **Intro cinematográfica (5.2s, pulável):** sequência original de boot
  do sistema, consciente do tema, com SFX sintetizados localmente
  (`jarvis/ui/hub/assets/sfx/*.wav`, gerados por `sfx.py` — zero áudio
  copiado, zero música). Qualquer tecla/clique pula.
- **5 temas reais** (azul, vermelho, verde, amarelo, cinza): núcleo, HUD,
  brilhos, partículas, textos, bordas, botões, indicadores, estados e intro.
- **Central de configurações** (6 abas: aparência, voz, microfone,
  comandos, inicialização, sistema): todo controle aplica + salva +
  restaura; nada é falso. Versão exibida vem de `jarvis.__version__`.
- **F11** alterna fullscreen; layout responsivo 800×560 → 2560×1440;
  DPI do Windows com `PassThrough` (125%/150%/175%/200% sem arredondar).
- **Instância única:** segunda execução foca a janela existente.
- **Autostart real:** liga/desliga via `HKCU\...\Run` (Windows), reversível.
  No EXE empacotado registra o próprio `.exe`; em desenvolvimento,
  `python main.py --hub`.
- **Voz↔UI integrada:** falar/ouvir atualiza núcleo, badge e HUD via
  `EventBus`; workers fora da thread da UI — a interface nunca congela.

Re-shot visual (receita da auditoria): rode o HUB em offscreen, chame
`hub.apply_theme(tid, persist=False)` por tema, capture `grab()` do núcleo
nos 8 estados + intro — compare com a baseline antes de cada commit visual.

---

## 10. Build do .EXE

```bat
REM no Windows, com Python 3.10+:
pip install -r requirements.txt -r requirements-voice.txt -r requirements-ui.txt -r requirements-build.txt
build.bat
```

`build.bat` → `python build.py` (10 etapas: Python, dependências, limpa
`build/`+`dist/`, roda a suíte, gera ícone `.ico` sintetizado, PyInstaller
via `jarvis.spec`, pasta `models/`, extras, valida o EXE, smoke `--version`).
Empacotamento **one-dir**:

```
dist\JARVIS\J.A.R.V.I.S.exe
dist\JARVIS\_internal\
dist\JARVIS\models\LEIA-ME.txt
dist\JARVIS\BUILD_INFO.txt
dist\JARVIS\README.md
```

Sem console (`console=False`), sem UPX. Voz incluída somente se instalada
no build (lazy-imports preservados). Fora do Windows, `build.py` roda em
**modo verificação** (testes + ícone + `build/BUILD_INFO.txt`, sem
PyInstaller).

**REQUER VALIDAÇÃO NO WINDOWS:** o arquivo `dist\JARVIS\J.A.R.V.I.S.exe`
só pode ser gerado e executado em uma máquina Windows. O smoke test do
build (`--cli --version`) confirma que o processo sobe e sai com código 0;
como o EXE é windowed, a stdout pode ser vazia — o código de saída é o
critério. Roteiro manual no Windows: abrir, intro, HUB, `que horas são?`
digitado, F11, trocar tema, segunda instância foca a primeira, fechar limpo.

---

## 11. Auditoria de bugs

`docs/BUG_AUDIT.md` — 4 ciclos de caça (núcleo sob estresse, HUB Qt,
corridas/interrupções, finalização), scripts em `docs/audit/`.
Bugs reais encontrados foram corrigidos com teste de regressão + regra
permanente para PRs futuros.

---

## 12. Como baixar / distribuir

Leia **`DOWNLOAD_JARVIS.txt`** (instruções em linguagem simples).

Pacote para copiar: `JARVIS_RELEASE.zip` (raiz do repositório).

O executável Windows **`dist\JARVIS\J.A.R.V.I.S.exe`** só é gerado em um
PC Windows (`build.bat`). Este repositório **não** contém um link de
download inventado e **não** inclui um `.exe` pré-compilado.

## 13. Filosofia e proibições

- Sem OpenAI/LLM/APIs de IA, sem STT/TTS online, sem nuvem obrigatória.
- Entrada do usuário **nunca** é executada como shell: só ações registradas.
- Confirmar antes de reiniciar/desligar/fechar.
- Sem placeholders, sem botão falso, sem "parece funcionar".
