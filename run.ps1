# YouTube MP3 Downloader - Startup Script (PowerShell)

Write-Host "YouTube MP3 Downloader"
Write-Host "=========================="
Write-Host ""

# Check if venv exists
if (-not (Test-Path "venv")) {
    Write-Host "Virtual environment not found!" -ForegroundColor Red
    Write-Host "Run: python -m venv venv; venv\Scripts\Activate.ps1; pip install -r requirements.txt"
    exit 1
}

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$venvPip = Join-Path $PSScriptRoot "venv\Scripts\pip.exe"

# Check if dependencies are installed
& $venvPython -c "import fastapi" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..."
    & $venvPip install -r requirements.txt
}

# Get local IP (first non-loopback IPv4 address)
$localIp = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -ne "127.0.0.1" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -First 1 -ExpandProperty IPAddress)

Write-Host "Starting server..."
Write-Host ""
Write-Host "Local:   http://localhost:8000"
if ($localIp) {
    Write-Host "Network: http://${localIp}:8000"
}
Write-Host ""
Write-Host "Press Ctrl+C to stop"
Write-Host ""

# Run the app (module form, since app/main.py uses absolute `app.*` imports)
& $venvPython -m app.main
