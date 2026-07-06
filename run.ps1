# Kaiwa launcher for Windows — starts Ollama, VOICEVOX (if installed), and the app server.
# Run with:  powershell -ExecutionPolicy Bypass -File run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Kaiwa - local Japanese tutor"
$port = if ($env:KAIWA_PORT) { $env:KAIWA_PORT } else { "8130" }

if (-not (Test-Path .venv)) { Write-Host "x run setup.ps1 first"; exit 1 }

# 1. Ollama
$ollamaUp = $false
try { Invoke-RestMethod http://localhost:11434/api/version -TimeoutSec 2 | Out-Null; $ollamaUp = $true } catch {}
if (-not $ollamaUp) {
  if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "> starting ollama..."
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    foreach ($i in 1..20) {
      try { Invoke-RestMethod http://localhost:11434/api/version -TimeoutSec 1 | Out-Null; break } catch { Start-Sleep 1 }
    }
  } else {
    Write-Host "! Ollama not found - install from https://ollama.com/download (or use a cloud API key in Settings)"
  }
}

# 2. VOICEVOX (optional, better voices) — unzip the Windows CPU engine to vendor\windows-cpu\
if (Test-Path "vendor\windows-cpu\run.exe") {
  $vvUp = $false
  try { Invoke-RestMethod http://127.0.0.1:50021/version -TimeoutSec 2 | Out-Null; $vvUp = $true } catch {}
  if (-not $vvUp) {
    Write-Host "> starting VOICEVOX engine (takes ~20s)..."
    Start-Process "vendor\windows-cpu\run.exe" -ArgumentList "--host","127.0.0.1","--port","50021" -WindowStyle Hidden
  }
}

# 3. Tailscale HTTPS link (optional — lets your phone reach Kaiwa from anywhere)
$ts = "C:\Program Files\Tailscale\tailscale.exe"
if (Test-Path $ts) {
  & $ts serve --bg $port 2>$null | Out-Null
}

# 4. App server (0.0.0.0 so phones on the network can connect)
Write-Host "> starting Kaiwa at http://localhost:$port"
Start-Job { Start-Sleep 2; Start-Process "http://localhost:$using:port" } | Out-Null
& .venv\Scripts\python.exe -m uvicorn server.main:app --host 0.0.0.0 --port $port
