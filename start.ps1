param([int]$Port = 8000, [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$basePython = $null
$baseArgs = @()
if (!(Test-Path -LiteralPath $venvPython)) {
    $launcherCommand = Get-Command py -ErrorAction SilentlyContinue
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if ($launcherCommand) { $basePython = $launcherCommand.Source; $baseArgs = @('-3') }
    elseif ($pythonCommand -and !$pythonCommand.Source.Contains('WindowsApps')) { $basePython = $pythonCommand.Source }
    elseif (Test-Path -LiteralPath $bundledPython) { $basePython = $bundledPython }
    else { throw 'Can cai Python 3.11+ truoc khi chay project.' }
    & $basePython @baseArgs -m venv --without-pip .venv
    if ($LASTEXITCODE -ne 0) { throw 'Khong tao duoc virtual environment.' }
}
& $venvPython -c 'import numpy,pandas,scipy,sklearn,fastapi,uvicorn,tabulate,PIL,onnxruntime,multipart'
if ($LASTEXITCODE -ne 0) {
    & $venvPython -m ensurepip --upgrade
    if ($LASTEXITCODE -eq 0) {
        & $venvPython -m pip install -r requirements.txt
    } else {
        if (!$basePython) {
            $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
            if (Test-Path -LiteralPath $bundledPython) { $basePython = $bundledPython }
            else { throw 'Can pip de cai thu vien. Chay Python installer va bat tuy chon pip.' }
        }
        & $basePython @baseArgs -m pip --python $venvPython install -r requirements.txt
    }
    if ($LASTEXITCODE -ne 0) { throw 'Cai thu vien that bai. Kiem tra ket noi Internet.' }
}
if (!(Test-Path -LiteralPath (Join-Path $PSScriptRoot 'artifacts\engine.npz'))) {
    & $venvPython -m src.cli train
    if ($LASTEXITCODE -ne 0) { throw 'Huan luyen mo hinh that bai.' }
}
if ($PrepareOnly) { Write-Output 'Cine Cas Phile is ready.'; exit 0 }
Write-Output "Open http://127.0.0.1:$Port - Ctrl+C to stop."
& $venvPython -m src.cli serve --port $Port
exit $LASTEXITCODE
