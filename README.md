# JARVIS — Cross-Platform Multimodal Personal AI

> **One JARVIS, multiple clients and tools. Local-first, secure, and extensible.**

JARVIS is a distributed personal AI agent designed to run across desktop and mobile environments with a centralized brain, shared memory, multimodal perception, and safe computer control.

---

## Architecture & Roadmap

The system is developed incrementally following the architecture and roadmap blueprints:

- **Target Architecture**: [`docs/JARVIS_Full_Architecture.md`](docs/JARVIS_Full_Architecture.md)
- **Implementation Roadmap**: [`docs/JARVIS_Implementation_Roadmap.md`](docs/JARVIS_Implementation_Roadmap.md)

---

## Current Roadmap Phase

### **PART 0 — Project Foundation** :white_check_mark: Complete

- [x] Repository foundation and modular structure
- [x] Configuration system (`config.yaml`, `.env.example`, Pydantic models)
- [x] Structured console and rotating file logging (`data/logs/jarvis.log`)
- [x] Structured error handling hierarchy (`JarvisError`, `ConfigurationError`, `InitializationError`)
- [x] Test framework (`pytest`, fixtures, isolated configuration tests)
- [x] Application entry points (`python -m app`, `python main.py`)
- [x] Interactive terminal mode & completion status verification

### **PART 1 — JARVIS Core / Brain** :white_check_mark: Complete

- [x] Replaceable model abstraction layer (`BaseLLMProvider`, `ChatMessage`, `ModelResponse`)
- [x] LLM providers: local **Ollama** (`http://localhost:11434`) and deterministic zero-dependency **Mock Provider**
- [x] Central **Orchestrator** managing message lifecycle: `User -> Session -> Context -> Model -> Response -> Session`
- [x] In-memory **Session Management** with isolated conversation history
- [x] **Context Manager** assembling system prompts with sliding-window truncation
- [x] **Model Router** for task-based model selection
- [x] Multi-turn conversational terminal REPL loop with context retention
- [x] Graceful error recovery for model unavailability and request timeouts

### **PART 2 — Personality Engine** :white_check_mark: Complete

- [x] Modular personality subsystem (`app/personality/`) separated from core reasoning layer
- [x] Configurable trait spectrum: `humor`, `sarcasm`, `formality`, `warmth`, `verbosity`, `confidence`, `proactivity` (0.0 to 1.0)
- [x] Customizable `preferred_address` ("sir", "Dr. Banner", etc.) and `response_style` ("concise", "detailed")
- [x] 6 Standard Operating Modes with tailored profiles and trait overrides (`normal`, `coding`, `study`, `research`, `professional`, `emergency`)
- [x] Dynamic system prompt generation (`BehaviorEngine`) with non-negotiable safety invariant
- [x] Core orchestrator integration with dynamic context injection
- [x] Interactive runtime mode switching and trait adjustment commands in terminal REPL

### **PART 3 — Voice System** :white_check_mark: Complete

- [x] Clean audio I/O abstraction (`SoundDeviceAudioManager` & `VirtualAudioManager`) with physical device query
- [x] Adaptive RMS energy Voice Activity Detection (`EnergyVAD`) & stateful utterance segmentation (`VADSegmenter`)
- [x] Local wake-word detection engine (`KeywordWakeWordDetector`, `OpenWakeWordDetector`, `MockWakeWordDetector`)
- [x] Local offline Speech-to-Text powered by `faster-whisper` (`tiny.en` / `base.en`) with direct NumPy array streaming
- [x] Offline native Windows SAPI5 speech synthesis (`WindowsSapiTTSProvider`) with rate control and voice selection
- [x] Low-latency barge-in interruption controller (`InterruptionController`) that purges active playback upon user speech
- [x] End-to-end `VoicePipeline` coordinating $\text{Microphone} \rightarrow \text{Wake Word} \rightarrow \text{VAD} \rightarrow \text{STT} \rightarrow \text{Core} \rightarrow \text{TTS} \rightarrow \text{Speaker}$
- [x] Three operational modes: `text` (zero hardware overhead), `push_to_talk`, and continuous `wake_word`
- [x] Latency telemetry recording: speech duration, STT latency, LLM latency, TTS latency, and total round-trip time
- [x] CLI flags (`--voice`, `--voice-mode`) and in-session terminal REPL controls (`voice`, `voice on/off`, `listen`)

---

## Getting Started

### 1. Prerequisites

- Python 3.10+ (tested on Python 3.14.5)
- Windows 10/11
- Microphone & speakers (optional, zero-hardware mock fallbacks included for CI/headless environments)
- Optional: [Ollama](https://ollama.com/) for local LLM inference (e.g. `ollama run llama3.2`)

### 2. Environment Setup

```powershell
# Create virtual environment (if not already created)
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install foundation and voice dependencies
pip install -r requirements.txt
```

### 3. Configuration

Default settings reside in `config.yaml` and `app/config/personality.yaml`. To override settings using environment variables, copy `.env.example` to `.env`:

```powershell
cp .env.example .env
```

Available environment variables:
- **Core / Environment**:
  - `JARVIS_ENV`: `development`, `production`, `test`
  - `JARVIS_MODE`: `terminal`
  - `JARVIS_DEBUG`: `true` or `false`
  - `JARVIS_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Model Layer**:
  - `JARVIS_MODEL_PROVIDER`: `mock` (default for testing) or `ollama` (for local LLM)
  - `JARVIS_MODEL_NAME`: `llama3.2`, `mistral`, etc.
  - `JARVIS_MODEL_BASE_URL`: `http://localhost:11434`
  - `JARVIS_MODEL_TEMPERATURE`: float between `0.0` and `2.0`
  - `JARVIS_MODEL_FALLBACK`: `true` (falls back to mock if Ollama is unreachable)
- **Personality Engine**:
  - `JARVIS_PERSONALITY_NAME`: Default `"JARVIS"`
  - `JARVIS_PERSONALITY_MODE`: `normal`, `coding`, `study`, `research`, `professional`, `emergency`
  - `JARVIS_PERSONALITY_HUMOR`: float between `0.0` and `1.0`
  - `JARVIS_PERSONALITY_SARCASM`: float between `0.0` and `1.0`
  - `JARVIS_PERSONALITY_FORMALITY`: float between `0.0` and `1.0`
  - `JARVIS_PERSONALITY_WARMTH`: float between `0.0` and `1.0`
  - `JARVIS_PERSONALITY_VERBOSITY`: float between `0.0` and `1.0`
  - `JARVIS_PERSONALITY_CONFIDENCE`: float between `0.0` and `1.0`
  - `JARVIS_PERSONALITY_PROACTIVITY`: float between `0.0` and `1.0`
  - `JARVIS_PERSONALITY_ADDRESS`: Default `"sir"`
  - `JARVIS_PERSONALITY_STYLE`: Default `"concise"`
- **Voice Subsystem**:
  - `JARVIS_VOICE_ENABLED`: `true` or `false` (default: `false`)
  - `JARVIS_VOICE_MODE`: `text`, `push_to_talk`, or `wake_word`
  - `JARVIS_VOICE_STT_PROVIDER`: `faster-whisper` or `mock`
  - `JARVIS_VOICE_STT_MODEL`: `tiny.en`, `base.en`, etc.
  - `JARVIS_VOICE_STT_DEVICE`: `cpu` or `cuda`
  - `JARVIS_VOICE_TTS_PROVIDER`: `sapi5` or `mock`
  - `JARVIS_VOICE_TTS_VOICE`: `"Microsoft David Desktop"`, `"Microsoft Zira Desktop"`, etc.
  - `JARVIS_VOICE_TTS_SPEED`: float between `0.5` and `2.0` (default: `1.0`)
  - `JARVIS_VOICE_VAD_ENABLED`: `true` or `false`
  - `JARVIS_VOICE_WAKE_WORD_PHRASE`: `"jarvis"`

---

## Running JARVIS

### Interactive Terminal Mode (Text & Voice)

Start JARVIS in standard text mode:

```powershell
python -m app
# or
python main.py
```

Start JARVIS directly with the Voice Pipeline active:

```powershell
python -m app --voice
# or with a specific voice mode
python -m app --voice --voice-mode push_to_talk
```

#### In-Session Commands
- `status`: Display current core system, personality, and voice status
- `personality`: Display active personality profile and traits
- `voice`: Show active voice pipeline status and latest latency telemetry
- `voice on` / `voice off`: Enable or disable the voice pipeline at runtime
- `voice mode <mode>`: Switch voice mode (`text`, `push_to_talk`, `wake_word`)
- `listen`: Trigger a push-to-talk recording turn
- `mode <name>`: Switch operating mode (`normal`, `coding`, `study`, `research`, `professional`, `emergency`)
- `trait <name> <value>`: Adjust a personality trait dimension
- `reset`: Clear the active session conversation history
- `clear`: Clear the terminal screen
- `help`: Show available commands
- `exit` / `quit`: Shut down cleanly

### Status Check

Verify operational status from the terminal:

```powershell
python -m app --status
```
Output:
```text
JARVIS CORE ONLINE
Mode: terminal
Status: ready
Voice: disabled (mode=wake_word, stt=faster-whisper, tts=sapi5)
```

---

## Running Tests

Run the complete test suite (84 unit and integration tests):

```powershell
pytest -v
```

---

## Next Phase

**PART 4 — MEMORY SYSTEM** (Short-term memory, Working memory, Long-term memory, Semantic memory / Vector retrieval, Episodic memory, Preference memory, Project memory, SQLite / Chroma storage).
