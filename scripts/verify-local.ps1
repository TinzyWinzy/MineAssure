$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskConfig = Get-Content -Raw -LiteralPath (Join-Path $taskRoot '.local\config.json') | ConvertFrom-Json
$env:TEST_DATABASE_URL = "postgresql+psycopg://mineassure:$($taskConfig.database_password)@127.0.0.1:$($taskConfig.database_port)/mineassure_test"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
$env:ENVIRONMENT = 'test'
$env:SECRET_KEY = $taskConfig.secret_key
$taskPython = Join-Path $taskRoot 'apps\api\.venv\Scripts\python.exe'
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Verification failed: $Program $Arguments" }
}
Push-Location (Join-Path $taskRoot 'apps\api')
try {
    Invoke-Checked $taskPython @('-m', 'ruff', 'check', 'app', 'tests')
    Invoke-Checked $taskPython @('-m', 'ruff', 'format', '--check', 'app', 'tests')
    Invoke-Checked $taskPython @('-m', 'alembic', 'upgrade', 'head')
    Invoke-Checked $taskPython @('-m', 'alembic', 'check')
    Invoke-Checked $taskPython @('-m', 'mypy', 'app/engine.py', '--ignore-missing-imports')
    Invoke-Checked $taskPython @('-m', 'pytest', '-q', '--tb=short', '-x')
} finally { Pop-Location }
Push-Location (Join-Path $taskRoot 'apps\web')
try {
    Invoke-Checked 'npm.cmd' @('run', 'lint')
    Invoke-Checked 'npm.cmd' @('run', 'build')
} finally { Pop-Location }
