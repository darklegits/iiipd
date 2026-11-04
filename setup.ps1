param(
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venv = Join-Path $root ".venv"
if ($Recreate -and (Test-Path $venv)) {
    Remove-Item -LiteralPath $venv -Recurse -Force
}
if (-not (Test-Path $venv)) {
    python -m venv $venv
}

$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt

Write-Host ""
Write-Host "Готово. Запуск: .\run.ps1"
Write-Host "Если данных ещё нет:"
Write-Host "  .\.venv\Scripts\python.exe scripts\fetch_data.py"
Write-Host "  .\.venv\Scripts\python.exe scripts\train.py"
