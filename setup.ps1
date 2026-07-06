# Kaiwa one-time setup for Windows: Python env, dependencies, speech model, dictionary.
# Run with:  powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Kaiwa setup (Windows)"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "x Python 3.11+ is required - install from https://www.python.org/downloads/"
  Write-Host "  (tick 'Add python.exe to PATH' in the installer)"
  exit 1
}

if (-not (Test-Path .venv)) {
  Write-Host "> creating Python environment..."
  python -m venv .venv
}
Write-Host "> installing dependencies..."
& .venv\Scripts\python.exe -m pip install -q --upgrade pip
& .venv\Scripts\pip.exe install -q -r requirements.txt

New-Item -ItemType Directory -Force -Path data, models, vendor | Out-Null

# whisper.cpp speech-recognition model (~466 MB)
if (-not (Test-Path models\ggml-small.bin)) {
  Write-Host "> downloading speech-recognition model (466 MB)..."
  curl.exe -L --progress-bar -o models\ggml-small.bin `
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
}

# JMdict dictionary (latest jmdict-simplified English release)
if (-not (Get-ChildItem models -Filter "jmdict-eng-*.json" -ErrorAction SilentlyContinue)) {
  Write-Host "> downloading JMdict dictionary..."
  try {
    $rel = Invoke-RestMethod https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest
    $asset = $rel.assets | Where-Object { $_.name -match '^jmdict-eng-[0-9].*\.json\.zip$' } | Select-Object -First 1
    curl.exe -L --progress-bar -o "$env:TEMP\kaiwa-jmdict.zip" $asset.browser_download_url
    Expand-Archive -Force "$env:TEMP\kaiwa-jmdict.zip" models
    Remove-Item "$env:TEMP\kaiwa-jmdict.zip"
  } catch {
    Write-Host "! couldn't fetch JMdict - download a jmdict-eng-*.json from"
    Write-Host "  https://github.com/scriptin/jmdict-simplified/releases into models\"
  }
}

# whisper.cpp Windows binary (for voice input)
$hasWhisper = (Get-Command whisper-cli -ErrorAction SilentlyContinue) -or
              (Test-Path vendor\whisper\whisper-cli.exe) -or (Test-Path vendor\whisper\main.exe) -or
              (Test-Path vendor\whisper\Release\whisper-cli.exe) -or (Test-Path vendor\whisper\Release\main.exe)
if (-not $hasWhisper) {
  Write-Host "> downloading whisper.cpp (voice input)..."
  try {
    $rel = Invoke-RestMethod https://api.github.com/repos/ggerganov/whisper.cpp/releases/latest
    $asset = $rel.assets | Where-Object { $_.name -match 'whisper-bin-x64\.zip$' } | Select-Object -First 1
    curl.exe -L --progress-bar -o "$env:TEMP\kaiwa-whisper.zip" $asset.browser_download_url
    Expand-Archive -Force "$env:TEMP\kaiwa-whisper.zip" vendor\whisper
    Remove-Item "$env:TEMP\kaiwa-whisper.zip"
  } catch {
    Write-Host "! couldn't fetch whisper.cpp - download the Windows x64 build from"
    Write-Host "  https://github.com/ggerganov/whisper.cpp/releases and unzip into vendor\whisper\"
  }
}

# Japanese voice hint (Windows TTS fallback when VOICEVOX isn't installed)
Write-Host ""
Write-Host "Tip: for spoken replies without VOICEVOX, add a Japanese voice to Windows:"
Write-Host "     Settings > Time & Language > Language > add Japanese (with Speech)"
Write-Host ""
Write-Host "setup complete - start Kaiwa with:  powershell -ExecutionPolicy Bypass -File run.ps1"
