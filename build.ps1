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

# PyInstaller очищает папку назначения, поэтому сохраняем только данные
# (data: история и кэш). Логи и временные профили Chrome копировать нельзя:
# открытый браузер держит файлы профиля, и копирование падает.
$userdata = Join-Path $appDir "userdata"
$userdataData = Join-Path $userdata "data"
$userdataBackup = Join-Path $root ".cache\userdata-backup"
if (Test-Path $userdataBackup) {
    Remove-Item $userdataBackup -Recurse -Force
}
$hasUserdata = Test-Path $userdataData
if ($hasUserdata) {
    # Копирование вместо Move-Item: переименование каталога может быть
    # запрещено политикой рабочей папки, а чтение и копирование — нет.
    Copy-Item $userdataData $userdataBackup -Recurse -Force
}

# PyInstaller удаляет dist целиком, а Chrome из окна приложения держит файлы
# профиля в userdata\ChromeProfile-*. Закрываем окно и убираем профили,
# иначе сборка падает с «файл занят другим процессом».
if (Test-Path $userdata) {
    Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class OracleWindowCloser {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hWnd, StringBuilder text, int max);
    [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr hWnd, uint msg, IntPtr w, IntPtr l);
    public static void CloseAppWindows() {
        EnumWindows((h, l) => {
            if (IsWindowVisible(h)) {
                var text = new StringBuilder(512);
                GetWindowTextW(h, text, 512);
                var title = text.ToString();
                if (title.StartsWith("127.0.0.1") || title.StartsWith("Погодный оракул")) {
                    PostMessageW(h, 0x0010, IntPtr.Zero, IntPtr.Zero);
                }
            }
            return true;
        }, IntPtr.Zero);
    }
}
"@ -ErrorAction SilentlyContinue
    try { [OracleWindowCloser]::CloseAppWindows() } catch { }
    # Само приложение тоже останавливаем: иначе оно держит Chrome и профиль.
    Get-Process WeatherOracle -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    # Chrome в режиме приложения может остаться фоновыми процессами и держать
    # профиль. Останавливаем только те процессы, чей путь ведёт в userdata.
    try {
        Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction Stop |
            Where-Object { $_.CommandLine -and $_.CommandLine -like "*$userdata*" } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch { }
    Start-Sleep -Seconds 3
    Get-ChildItem $userdata -Directory -Filter "ChromeProfile-*" -ErrorAction SilentlyContinue | ForEach-Object {
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            if (-not (Test-Path $_.FullName)) { break }
            Start-Sleep -Milliseconds 500
        }
    }
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

if ($hasUserdata -and (Test-Path $userdataBackup) -and -not (Test-Path $userdataData)) {
    New-Item -ItemType Directory -Force -Path $userdata | Out-Null
    Copy-Item $userdataBackup $userdataData -Recurse -Force
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
# Start-Process для GUI-EXE может ждать оболочку Windows бесконечно;
# запускаем процесс напрямую и ждём его завершения.
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $exe
$startInfo.Arguments = "--smoke-test"
$startInfo.UseShellExecute = $false
$startInfo.WorkingDirectory = $appDir
$proc = [System.Diagnostics.Process]::Start($startInfo)
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
