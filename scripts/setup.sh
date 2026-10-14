#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

command -v python3 >/dev/null || { echo "Python 3.11+ is required."; exit 1; }
command -v node >/dev/null || { echo "Node.js 20+ is required."; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
node -e 'const major = Number(process.versions.node.split(".")[0]); if (major < 20) process.exit(1)'

if ! command -v ffmpeg >/dev/null; then
  echo "Warning: FFmpeg was not found. Install it and add it to PATH before processing recordings."
fi
if ! command -v ollama >/dev/null; then
  echo "Warning: Ollama was not found. Install it from https://ollama.com/download before generating minutes."
fi

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt
(cd frontend && npm install)
.venv/bin/python -c 'import sys; sys.path.insert(0, "backend"); from app.main import app; print("SQLite database initialized")'

cat <<'EOF'
Setup complete. Optional local AI dependencies are intentionally not downloaded automatically.
Install faster-whisper and DeepFilterNet in .venv when needed, then run:
  ollama pull qwen3:8b
Start with: ./scripts/start.sh
EOF
