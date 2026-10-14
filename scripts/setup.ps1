$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.11+ is required." }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 20+ is required." }
$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$pyVersion -lt [version]"3.11") { throw "Python 3.11+ is required." }
$nodeMajor = node -p "process.versions.node.split('.')[0]"
if ([int]$nodeMajor -lt 20) { throw "Node.js 20+ is required." }

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Warning "FFmpeg was not found. Install it and add it to PATH." }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { Write-Warning "Ollama was not found. Install it from https://ollama.com/download." }
if (-not (Test-Path ".venv\Scripts\python.exe")) { python -m venv .venv }
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Push-Location frontend; npm install; Pop-Location
& .venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend'); from app.main import app; print('SQLite database initialized')"
Write-Host "Setup complete. Install optional faster-whisper/DeepFilterNet packages when needed, then run: ollama pull qwen3:8b"
