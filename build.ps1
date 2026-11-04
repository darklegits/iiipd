$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = "python"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
}

$buildTools = Join-Path $root ".buildtools"
if (-not (Test-Path $buildTools)) {
    Write-Host "Устанавливаю PyInstaller в .buildtools..."
    & $python -m pip install --target $buildTools -r requirements-build.txt
}

$pythonPath = @($buildTools)
$vendor = Join-Path $root ".vendor"
if (Test-Path $vendor) {
    $pythonPath += $vendor
}
$env:PYTHONPATH = ($pythonPath -join ";")

& $python -m PyInstaller WeatherOracle.spec --noconfirm --clean --distpath dist --workpath build

Write-Host ""
Write-Host "Готово: dist\WeatherOracle\WeatherOracle.exe"
Write-Host "Запускайте exe из этой папки, не отделяя его от _internal."
