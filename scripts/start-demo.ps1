$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'start-local.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Native demo startup failed; see docs/local-development.md and .local logs.' }
