param(
    [int]$Port = 8000,
    [string]$HostAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$env:MPLCONFIGDIR = Join-Path $root ".cache\matplotlib"
New-Item -ItemType Directory -Force -Path $env:MPLCONFIGDIR | Out-Null

# Локальная папка зависимостей нужна только в ограниченных средах.
$vendor = Join-Path $root ".vendor"
if (Test-Path $vendor) {
    $env:PYTHONPATH = $vendor
}

$python = "python"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
}

Write-Host "Погодный оракул: http://${HostAddress}:$Port"
Write-Host "Swagger UI:      http://${HostAddress}:$Port/docs"
& $python -m uvicorn app.main:app --host $HostAddress --port $Port
