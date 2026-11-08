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
    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось установить PyInstaller (код $LASTEXITCODE)"
    }
}

$pythonPath = @($buildTools)
$vendor = Join-Path $root ".vendor"
if (Test-Path $vendor) {
    $pythonPath += $vendor
}
$env:PYTHONPATH = ($pythonPath -join ";")

$distRoot = Join-Path $root "dist"
$appDir = Join-Path $distRoot "WeatherOracle"
$exe = Join-Path $appDir "WeatherOracle.exe"
$pythonDll = Join-Path $appDir "_internal\python313.dll"

# Промежуточные файлы PyInstaller держим вне папки build: иначе в дереве
# проекта остаётся похожий на вид WeatherOracle.exe без _internal, и его
# случайный запуск даёт «Failed to load Python DLL ... python313.dll».
$workDir = Join-Path $root ".cache\pyinstaller"

# PyInstaller очищает папку назначения, поэтому userdata (логи и
# обновлённую историю) сохраняем и возвращаем на место после сборки.
$userdata = Join-Path $appDir "userdata"
$userdataBackup = Join-Path $root ".cache\userdata-backup"
if (Test-Path $userdataBackup) {
    Remove-Item $userdataBackup -Recurse -Force
}
$hasUserdata = Test-Path $userdata
if ($hasUserdata) {
    # Копирование вместо Move-Item: переименование каталога может быть
    # запрещено политикой рабочей папки, а чтение и копирование — нет.
    Copy-Item $userdata $userdataBackup -Recurse -Force
}

Write-Host "Собираю приложение..."
& $python -m PyInstaller WeatherOracle.spec --noconfirm --clean --distpath $distRoot --workpath $workDir
$buildCode = $LASTEXITCODE
if ($buildCode -ne 0) {
    throw "PyInstaller завершился с кодом $buildCode"
}

if (-not (Test-Path $exe)) {
    throw "Не найден EXE: $exe"
}
if (-not (Test-Path $pythonDll)) {
    throw "В сборке нет _internal\python313.dll — приложение не запустится: $pythonDll"
}

Copy-Item (Join-Path $root "build_assets\README-dist.txt") (Join-Path $appDir "README.txt") -Force

if ($hasUserdata -and (Test-Path $userdataBackup) -and -not (Test-Path $userdata)) {
    Copy-Item $userdataBackup $userdata -Recurse -Force
}
if (Test-Path $userdataBackup) {
    Remove-Item $userdataBackup -Recurse -Force
}

# Старая раскладка сборки: в D:\...\build оставался exe без _internal.
$legacyBuild = Join-Path $root "build"
if (Test-Path $legacyBuild) {
    Write-Host "Удаляю устаревшую папку build (в ней лежал нерабочий exe): $legacyBuild"
    Remove-Item $legacyBuild -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Проверяю запуск: $exe --smoke-test"
$proc = Start-Process -FilePath $exe -ArgumentList "--smoke-test" -PassThru
if (-not $proc.WaitForExit(240000)) {
    try { $proc.Kill() } catch { }
    throw "EXE не завершил smoke-test за 4 минуты"
}
if ($proc.ExitCode -ne 0) {
    throw "EXE не прошёл smoke-test (код $($proc.ExitCode)). Смотрите $appDir\userdata\oracle.log"
}

Write-Host ""
Write-Host "Готово: $exe"
Write-Host "Запускайте именно этот файл. Папка build больше не создаётся."
Write-Host "Переносите папку dist\WeatherOracle целиком, вместе с _internal и userdata."
