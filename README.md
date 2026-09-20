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

---

## Getting Started

### 1. Prerequisites

- Python 3.10+ (tested on Python 3.14.5)
- Windows 10/11

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

---

## Running JARVIS

### Interactive Terminal Mode

Start JARVIS in terminal mode:

```powershell
python -m app
```
or via the root launcher:
```powershell
python main.py
```

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

Validate paths and settings without launching the terminal loop:

```powershell
python -m app --check
```

---

## Running Tests

Run the complete test suite:

```powershell
pytest -v
```

---

## Project Structure

```text
JARVIS/
│
├── app/
│   ├── config/              # Configuration schemas & settings loader
│   ├── core/                # Core foundation: logging, exceptions, banners
│   ├── agents/              # Autonomous agent workflows (future phases)
│   ├── api/                 # Multi-device API gateway (future phases)
│   ├── events/              # Event bus & proactive triggers (future phases)
│   ├── integrations/        # External services (future phases)
│   ├── memory/              # Short/long-term & semantic memory (future phases)
│   ├── safety/              # Permissions & security sandboxing (future phases)
│   ├── tools/               # Tool registry & executors (future phases)
│   ├── vision/              # Screen & camera perception (future phases)
│   └── voice/               # Wake word, STT, TTS (future phases)
│
├── clients/                 # Desktop and mobile clients
├── data/                    # Local data directories (logs, memory, documents)
│   └── logs/                # Rotating logs (jarvis.log)
├── docs/                    # Architecture documents and specifications
├── tests/                   # Automated test suite
├── .env.example             # Environment variables template
├── config.yaml              # Core configuration file
├── requirements.txt         # Pinned foundation dependencies
├── main.py                  # Root application launcher
└── README.md                # Project documentation
```

---

## Next Phase

**PART 1 — JARVIS Core / Brain** (Orchestrator, Session Manager, Context Manager, Replaceable Model Interface & Router).
