$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22 or later, then run this launcher again.' }
if (-not (Test-Path -LiteralPath 'node_modules/mongodb/package.json')) {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Website build failed.' }
Write-Host 'Cine (cas) phile. 1.0: http://127.0.0.1:8001'
& npm.cmd run dev
