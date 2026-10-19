# J.A.R.V.I.S. — Just A Rather Very Intelligent System

Assistente desktop para **Windows**, escrito em **Python**, **100% local e offline**:
nenhum LLM, nenhuma API de IA, nenhum áudio ou comando sai do computador.
A "inteligência" é determinística: regras, matching, aliases, intenções,
parâmetros, contexto e memória local — *"IA sem ser IA"*.

> Etapa atual: **1.2 — Fundação + Motor do J.A.R.V.I.S. + Voz Local**.
> Próxima etapa: HUB + Intro + Temas + Experiência Visual (a base aqui criada
> será preservada e consumida pelo HUB).

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
| `ui/` | CLI/REPL e GUI mínima (temporária até o HUB) |

### Estados reais (`STARTING → READY → IDLE → LISTENING → PROCESSING → EXECUTING → SPEAKING → READY`, com `ERROR → READY`)

Emitidos via `EventBus` para a UI futura; transições inválidas são rejeitadas
e registradas — o sistema nunca fica preso em `LISTENING`/`PROCESSING`/`EXECUTING`.

---

## 2. Instalação

**Requisitos:** Python 3.10+ no Windows (desenvolvido/testado também em Linux).

```bat
REM núcleo (só stdlib + pytest p/ testes):
pip install -r requirements.txt

REM voz local (opcional, 100% offline após instalado):
pip install -r requirements-voice.txt
```

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
run.bat                  REM console interativa (Windows)
run.bat --gui            REM janela mínima (até o HUB chegar)

python main.py --exec "que horas são?"
python main.py --test-voice "J.A.R.V.I.S., abra o navegador."
python main.py --list-mics
python main.py --list-voices
python main.py --dry-run   REM simula ações sem executar (seguro)
```

Comandos do console: `:ouvir` (captura 1 fala), `:voz <texto>` (simula
transcrição), `:mics`, `:vozes`, `:estado`, `:ajuda`, `:sair`.

---

## 4. Como testar

```bat
python -m pytest tests/ -q
```

112 testes: normalização, matching, wake word (inclui o caso crítico
"comando após a wake word é preservado"), engine, aliases, contexto,
memória, confirmações, customs, storage, settings, estados, pipeline de voz
simulada, erros de voz e regressão texto==voz.

---

## 5. Comandos nativos

Abrir navegador, calculadora, bloco de notas, explorador, configurações,
Discord, sites/URLs (`"abra o youtube"`, `"abra o site https://..."`),
horas, data, minimizar/maximizar/tela-cheia, bloquear, **reiniciar**,
**desligar** e **fechar o J.A.R.V.I.S.** (os três últimos exigem "sim"/"não"),
além de `ajuda`.

### Adicionar comandos personalizados (via código; UI chega no HUB)

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

---

## 6. Voz local

- **Reconhecimento:** Vosk offline (`jarvis/voice/recognizer.py`).
  Modelo ausente/biblioteca ausente → motivo claro, modo texto preservado.
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

Logs detalhados sempre em `<dados>\logs\jarvis.log`.

---

## 9. Build do .EXE (preparação)

Dependências de build isoladas em `requirements-build.txt` (PyInstaller).
O código já evita caminhos absolutos, usa dados em `%APPDATA%` e lazy-imports
para voz — pronto para empacotamento na etapa de distribuição.

## 10. Filosofia e proibições

- Sem OpenAI/LLM/APIs de IA, sem STT/TTS online, sem nuvem obrigatória.
- Entrada do usuário **nunca** é executada como shell: só ações registradas.
- Confirmar antes de reiniciar/desligar/fechar.
