# Local Meeting Notes

A local-only meeting transcription and minutes workspace. Upload an MP3, WAV, or M4A recording, convert and optionally enhance it locally, transcribe with faster-whisper, and generate editable evidence-backed minutes with a local Ollama model.

No OpenAI, Azure OpenAI, Bedrock, paid API, telemetry, or cloud AI service is used. The backend binds to `127.0.0.1` by default.

## What is included

- React + TypeScript + Vite responsive review interface
- FastAPI + SQLAlchemy + SQLite backend
- Persisted single-worker background processing queue
- FFmpeg conversion to preserved 48 kHz and transcription-ready 16 kHz mono WAV files
- Optional DeepFilterNet noise reduction with safe fallback to the converted original
- faster-whisper integration with automatic CUDA/CPU selection, VAD, word timestamps, glossary prompt, and review flags
- Two-stage Ollama generation: timestamped evidence extraction, then structured final minutes using Pydantic JSON schemas
- Editable transcript and minutes, audio comparison, approval, and DOCX/TXT/JSON export
- Continuous transcript reading view with search highlighting and a single document editor
- Backend and frontend tests that mock local AI providers and never download models

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- FFmpeg on PATH
- Ollama installed locally for minutes generation
- Optional: NVIDIA CUDA runtime for faster transcription
- Optional: faster-whisper and DeepFilterNet installed in the backend virtual environment

The setup scripts deliberately do not download the large Whisper model or Ollama model automatically.

## Setup

### Windows PowerShell

```powershell
.\scripts\setup.ps1
ollama pull qwen3:8b
.\scripts\start.ps1
```

### macOS/Linux/Git Bash

```bash
./scripts/setup.sh
ollama pull qwen3:8b
./scripts/start.sh
```

Open `http://127.0.0.1:5173`. The API is available at `http://127.0.0.1:8000`.

### Optional local packages

Activate the virtual environment and install the packages for the capabilities you need:

```bash
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install faster-whisper
pip install DeepFilterNet
```

DeepFilterNet is optional. If it is absent or fails, the original uploaded file and converted WAV remain intact and the job continues using the converted original.

## Configuration

Copy `.env.example` to `.env` or set variables in the shell. Important settings are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MEETING_DATA_DIR` | `./data` | Local uploads, processed audio, exports, and database |
| `OLLAMA_URL` | `http://localhost:11434` | Local Ollama endpoint |
| `OLLAMA_MODEL` | `qwen3:8b` | Default local minutes model |
| `WHISPER_MODEL` | `large-v3-turbo` | Default transcription model |
| `MAX_UPLOAD_MB` | `500` | Upload size limit |
| `MAX_RECORDING_MINUTES` | `240` | Reserved recording duration setting |

Do not commit `data/`, model files, uploaded audio, transcripts, or Ollama data. The included `.gitignore` protects these paths.

## Reviewing a transcript

Open a meeting's review page to read the transcript as one continuous document. Search highlights matching text without hiding the rest of the conversation; use **Previous match** and **Next match** to move between results. Choose **Edit transcript** to make corrections in one text box, then **Save corrections**. Switching review tabs preserves unsaved corrections while the page stays open.

Existing recordings work with this view without retranscription. Corrections retain the timestamps of unaffected text; edits spanning original segment boundaries use the combined audio range. Save corrections before selecting **Regenerate minutes**, which uses the saved transcript.

## API

The backend exposes the requested `/api/meetings` CRUD/process/review/export routes plus:

- `GET /api/health`
- `GET /api/system-check?model=qwen3:8b`
- `POST /api/meetings/{id}/cancel`
- `GET /api/meetings/{id}/audio/{original|enhanced|selected}`

`/api/system-check` reports FFmpeg, DeepFilterNet, Ollama/model availability, CUDA/Whisper runtime, and free disk space. It never returns credentials or transcript content.

## Tests and checks

```bash
# Backend
.venv/bin/python -m pytest backend/tests -q

# Frontend
cd frontend
npm test
npm run lint
npm run build
```

The tests mock faster-whisper, DeepFilterNet, and Ollama boundaries. They do not need a GPU, model download, Ollama server, or audio fixture.

## Troubleshooting

- **FFmpeg not found:** install FFmpeg, add its `bin` directory to PATH, restart the shell, then retry.
- **Windows FFmpeg PATH still not visible:** set `FFMPEG_PATH` and `FFPROBE_PATH` to the full executable paths in `.env`, then restart the backend.
- **Ollama unavailable:** start Ollama and check `http://localhost:11434/api/tags`; the UI will show the exact `ollama pull qwen3:8b` command when the model is missing.
- **CUDA unavailable:** the app automatically uses CPU/INT8. Install a compatible NVIDIA driver, CUDA runtime, and PyTorch build if GPU acceleration is desired.
- **CUDA out of memory:** choose `small` or `medium`, close other GPU applications, or run with CPU/INT8.
- **DeepFilterNet unavailable:** leave noise reduction enabled; the job falls back to the converted original and records a warning.
- **Whisper model download failure:** verify local disk, network access needed only for the first model download, and the model name. Models are cached locally by faster-whisper.
- **Slow CPU transcription:** use `small`, shorten recordings, or install a supported CUDA stack. Processing remains in the background.
- **Windows path issues:** use the PowerShell scripts, keep the project path simple, and confirm FFmpeg/Ollama are available in the same PowerShell session.

## Privacy boundaries

Audio is stored under the configured local data directory with UUID filenames. Filenames are sanitized, extensions and MIME types are checked, and path traversal is rejected. Transcript contents are not written to application logs. Speaker diarization, speaker identity inference, attendee detection, and anonymous speaker labels are intentionally not implemented.
