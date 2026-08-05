# Starts the backend and frontend in separate windows.
#   .\dev.ps1
$root = $PSScriptRoot

Start-Process powershell -ArgumentList @(
  '-NoExit', '-Command',
  "Set-Location '$root\backend'; uv run uvicorn app.main:app --reload --port 8000"
)

Start-Process powershell -ArgumentList @(
  '-NoExit', '-Command',
  "Set-Location '$root\frontend'; npm run dev"
)

Write-Host ''
Write-Host '  Backend  http://127.0.0.1:8000  (API docs at /docs)' -ForegroundColor Cyan
Write-Host '  Frontend http://localhost:5173' -ForegroundColor Cyan
Write-Host ''
