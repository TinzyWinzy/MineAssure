#Requires -Version 7.0
param(
    [string]$PgBinPath,
    [int]$DatabasePort = 55432,
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskLocal = Join-Path $taskRoot '.local'
New-Item -ItemType Directory -Path $taskLocal -Force | Out-Null
if (-not $PgBinPath) { $PgBinPath = Join-Path $taskLocal 'pgsql\bin' }
$taskPgCtl = Join-Path $PgBinPath 'pg_ctl.exe'
if (-not (Test-Path -LiteralPath $taskPgCtl)) {
    throw 'PostgreSQL binaries missing. Extract the official Windows archive into .local (pgsql/bin), or pass -PgBinPath to an existing PostgreSQL 16+ bin directory. See docs/local-development.md.'
}
$taskPython = Join-Path $taskRoot 'apps\api\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Create apps/api/.venv and install apps/api with development dependencies first. See docs/local-development.md.'
}
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Program ($LASTEXITCODE)" }
}
$taskConfigFile = Join-Path $taskLocal 'config.json'
if (Test-Path -LiteralPath $taskConfigFile) {
    $taskConfig = Get-Content -Raw -LiteralPath $taskConfigFile | ConvertFrom-Json
    if ($taskConfig.database_port -ne $DatabasePort) { throw 'Reuse the existing database port from .local/config.json, or use a separate checkout.' }
} else {
    $taskConfig = [pscustomobject]@{
        database_port = $DatabasePort
        database_password = [guid]::NewGuid().ToString('N')
        secret_key = ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
    }
    $taskConfig | ConvertTo-Json | Set-Content -LiteralPath $taskConfigFile
}
$taskData = Join-Path $taskLocal 'pgdata'
if ((Test-Path -LiteralPath (Join-Path $taskData 'PG_VERSION')) -and -not (Test-Path -LiteralPath (Join-Path $taskData 'global\pg_control'))) {
    throw 'An incomplete local cluster exists. Preserve it under another name and initialize a fresh .local/pgdata directory; do not overwrite an existing cluster.'
}
if (-not (Test-Path -LiteralPath (Join-Path $taskData 'PG_VERSION'))) {
    $taskPasswordFile = Join-Path $taskLocal 'init-password.tmp'
    try {
        Set-Content -LiteralPath $taskPasswordFile -Value $taskConfig.database_password -NoNewline
        Invoke-Checked (Join-Path $PgBinPath 'initdb.exe') @('-D', $taskData, '-U', 'mineassure', '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C', "--pwfile=$taskPasswordFile")
        Add-Content -LiteralPath (Join-Path $taskData 'postgresql.conf') -Value "`nlisten_addresses = '127.0.0.1'`nport = $DatabasePort`n"
    } finally {
        if (Test-Path -LiteralPath $taskPasswordFile) { Remove-Item -LiteralPath $taskPasswordFile }
    }
}
& $taskPgCtl -D $taskData status *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Checked $taskPgCtl @('-D', $taskData, '-l', (Join-Path $taskLocal 'postgres.log'), '-w', 'start')
}
$taskOldPassword = $env:PGPASSWORD
try {
    $env:PGPASSWORD = $taskConfig.database_password
    foreach ($taskDatabase in @('mineassure', 'mineassure_test')) {
        $taskExists = & (Join-Path $PgBinPath 'psql.exe') -h 127.0.0.1 -p $DatabasePort -U mineassure -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$taskDatabase'"
        if ($LASTEXITCODE -ne 0) { throw 'Cannot connect to the project-local PostgreSQL instance' }
        if ($taskExists -ne '1') {
            Invoke-Checked (Join-Path $PgBinPath 'createdb.exe') @('-h', '127.0.0.1', '-p', "$DatabasePort", '-U', 'mineassure', $taskDatabase)
        }
    }
} finally { $env:PGPASSWORD = $taskOldPassword }
$env:DATABASE_URL = "postgresql+psycopg://mineassure:$($taskConfig.database_password)@127.0.0.1:$DatabasePort/mineassure"
$env:ENVIRONMENT = 'development'
$env:SECRET_KEY = $taskConfig.secret_key
$env:CORS_ORIGINS = "http://localhost:$WebPort,http://127.0.0.1:$WebPort"
Push-Location (Join-Path $taskRoot 'apps\api')
try {
    Invoke-Checked $taskPython @('-m', 'alembic', 'upgrade', 'head')
    Invoke-Checked $taskPython @('seed.py')
} finally { Pop-Location }
$taskProcessesFile = Join-Path $taskLocal 'processes.json'
if (Test-Path -LiteralPath $taskProcessesFile) {
    $taskProcesses = Get-Content -Raw -LiteralPath $taskProcessesFile | ConvertFrom-Json
    $taskLiveCount = 0
    foreach ($taskKind in @('api', 'web', 'worker')) {
        $taskProcess = Get-Process -Id $taskProcesses."${taskKind}_pid" -ErrorAction SilentlyContinue
        if ($taskProcess -and $taskProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$taskProcesses."${taskKind}_started").ToUniversalTime().Ticks) { $taskLiveCount++ }
    }
    if ($taskLiveCount -eq 3) {
        Write-Output "API already running. App: http://localhost:$WebPort (use scripts/stop-local.ps1 before changing ports)."
        exit 0
    }
    if ($taskLiveCount -gt 0) { throw 'Only some recorded services are running. Use scripts/stop-local.ps1 before restarting.' }
}
$taskVite = Join-Path $taskRoot 'apps\web\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $taskVite)) { throw 'Run npm ci from apps/web first.' }
foreach ($taskPort in @($ApiPort, $WebPort)) {
    $taskSocket = [System.Net.Sockets.TcpClient]::new()
    try {
        $taskSocket.Connect('127.0.0.1', $taskPort)
        throw "Port $taskPort is occupied by an untracked service. Stop that service or choose another port."
    } catch [System.Net.Sockets.SocketException] {
        # Connection refused means the port is available for this local service.
    } finally { $taskSocket.Dispose() }
}
$taskApi = Start-Process -FilePath $taskPython -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$ApiPort") -WorkingDirectory (Join-Path $taskRoot 'apps\api') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskLocal 'api.log') -RedirectStandardError (Join-Path $taskLocal 'api-error.log')
$taskWorker = Start-Process -FilePath $taskPython -ArgumentList @('-m', 'app.worker') -WorkingDirectory (Join-Path $taskRoot 'apps\api') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskLocal 'worker.log') -RedirectStandardError (Join-Path $taskLocal 'worker-error.log')
$env:API_PROXY_TARGET = "http://127.0.0.1:$ApiPort"
$taskNode = (Get-Command node -ErrorAction Stop).Source
$taskWeb = Start-Process -FilePath $taskNode -ArgumentList @('node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', "$WebPort", '--strictPort') -WorkingDirectory (Join-Path $taskRoot 'apps\web') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskLocal 'web.log') -RedirectStandardError (Join-Path $taskLocal 'web-error.log')
@{ worker_pid = $taskWorker.Id; worker_started = $taskWorker.StartTime.ToUniversalTime().ToString('o'); api_pid = $taskApi.Id; web_pid = $taskWeb.Id; api_started = $taskApi.StartTime.ToUniversalTime().ToString('o'); web_started = $taskWeb.StartTime.ToUniversalTime().ToString('o'); pg_bin = $PgBinPath; api_port = $ApiPort; web_port = $WebPort } | ConvertTo-Json | Set-Content -LiteralPath $taskProcessesFile
for ($taskAttempt = 0; $taskAttempt -lt 30; $taskAttempt++) {
    try {
        $taskReady = Invoke-RestMethod "http://127.0.0.1:$ApiPort/ready"
        $taskResponse = Invoke-WebRequest "http://127.0.0.1:$WebPort" -UseBasicParsing
        if ($taskReady.status -eq 'ready' -and $taskResponse.StatusCode -eq 200) {
            Write-Output "MineAssure: http://localhost:$WebPort | API: http://127.0.0.1:$ApiPort/docs"
            Write-Output 'Synthetic accounts use password demo. Runtime logs and local credentials are in ignored .local/.'
            exit 0
        }
    } catch { Start-Sleep -Seconds 1 }
}
throw 'Services did not become ready. Inspect .local/*-error.log and run scripts/stop-local.ps1 before retrying.'
