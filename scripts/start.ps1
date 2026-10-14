$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "Run .\scripts\setup.ps1 first." }
$sitePackages = Join-Path $Root ".venv\Lib\site-packages"
$cudaDllDirectories = @(
  (Join-Path $sitePackages "nvidia\cublas\bin"),
  (Join-Path $sitePackages "nvidia\cudnn\bin")
) | Where-Object { Test-Path $_ }
if ($cudaDllDirectories.Count -gt 0) {
  $env:PATH = (($cudaDllDirectories -join ";") + ";" + $env:PATH)
}
$backend = Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000" -PassThru
try {
  Push-Location frontend
  npm run dev -- --host 127.0.0.1
} finally {
  Pop-Location
  if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id }
}
