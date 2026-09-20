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

---

## Getting Started

### 1. Prerequisites

- Python 3.10+ (tested on Python 3.14.5)
- Windows 10/11
- Optional: [Ollama](https://ollama.com/) for local LLM inference (e.g. `ollama run llama3.2`)

### 2. Environment Setup

```powershell
# Create virtual environment (if not already created)
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install foundation dependencies
pip install -r requirements.txt
```

### 3. Configuration

Default settings reside in `config.yaml`. To override settings using environment variables, copy `.env.example` to `.env`:

```powershell
cp .env.example .env
```

Available environment variables:
- `JARVIS_ENV`: `development`, `production`, `test`
- `JARVIS_MODE`: `terminal`
- `JARVIS_DEBUG`: `true` or `false`
- `JARVIS_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `JARVIS_MODEL_PROVIDER`: `mock` (default for testing) or `ollama` (for local LLM)
- `JARVIS_MODEL_NAME`: `llama3.2`, `mistral`, etc.
- `JARVIS_MODEL_BASE_URL`: `http://localhost:11434`
- `JARVIS_MODEL_TEMPERATURE`: float between `0.0` and `2.0`
- `JARVIS_MODEL_FALLBACK`: `true` (falls back to mock if Ollama is unreachable)

---

## Running JARVIS

### Interactive Terminal Conversation Mode

Start JARVIS and interact directly with the Core Intelligence Layer:

```powershell
python -m app
# or
python main.py
```

Example session:
```text
JARVIS> Explain recursion.

JARVIS: Recursion is a programming concept where a function calls itself directly or indirectly to solve smaller instances of a problem. Every recursive function must define a base case to terminate execution and prevent infinite stack overflow.

JARVIS> What did I just ask you?

JARVIS: You previously asked: 'Explain recursion.'
```

#### In-Session Commands
- `status`: Display current core system status
- `reset`: Clear the active session conversation history
- `clear`: Clear the terminal screen
- `help`: Show available commands
- `exit` / `quit`: Shut down JARVIS Core cleanly

### Status Check

Verify operational status:

```powershell
python -m app --status
```
Output:
```text
JARVIS CORE ONLINE
Mode: terminal
Status: ready
```

### Configuration Validation

Validate paths and settings without launching the conversation loop:

```powershell
python -m app --check
```

---

## Running Tests

Run the complete test suite (45 unit and integration tests):

```powershell
pytest -v
```

---

## Next Phase

**PART 2 — Personality Engine** (Persona configuration, Tone, Humor, Sarcasm, Formality, Verbosity, Operating Modes: Normal, Coding, Study, Research, Emergency).
