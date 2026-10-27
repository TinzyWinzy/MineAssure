#Requires -Version 7.0
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskLocal = Join-Path $taskRoot '.local'
$taskState = Join-Path $taskLocal 'processes.json'
if (Test-Path -LiteralPath $taskState) {
    $taskProcesses = Get-Content -Raw -LiteralPath $taskState | ConvertFrom-Json
    foreach ($taskKind in @('api', 'web', 'worker')) {
        $taskProcess = Get-Process -Id $taskProcesses."${taskKind}_pid" -ErrorAction SilentlyContinue
        if ($taskProcess -and $taskProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$taskProcesses."${taskKind}_started").ToUniversalTime().Ticks) {
            # Windows virtualenv launchers spawn a child Python process.
            $taskProcess.Kill($true)
            $taskProcess.WaitForExit(5000) | Out-Null
        }
    }
    $taskPgCtl = Join-Path $taskProcesses.pg_bin 'pg_ctl.exe'
    & $taskPgCtl -D (Join-Path $taskLocal 'pgdata') -m fast -w stop
    Remove-Item -LiteralPath $taskState
}
Write-Output 'Project-local services stopped. Database files are retained.'
