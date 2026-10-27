param([string]$OutputDirectory = 'backups')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backupRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
if (-not $backupRoot.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Backup output must stay inside the MineAssure workspace.'
}
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
Set-Location $projectRoot
$rehearsalId = [Guid]::NewGuid().ToString('N')
$rehearsalDatabase = 'restore_' + $rehearsalId
$archivePath = Join-Path $backupRoot ('mineassure-' + $rehearsalId + '.dump')
$containerArchive = '/tmp/mineassure-' + $rehearsalId + '.dump'

function Invoke-Compose {
    param([string[]]$ComposeArguments)
    & docker compose @ComposeArguments
    if ($LASTEXITCODE -ne 0) { throw ('Docker Compose failed: ' + $ComposeArguments[0]) }
}

# Use an isolated new database. Never restore over the source database.
Invoke-Compose @('exec', '-T', 'postgres', 'pg_dump', '-U', 'mineassure', '-d', 'mineassure', '-Fc', '-f', $containerArchive)
Invoke-Compose @('cp', "postgres:$containerArchive", $archivePath)
Invoke-Compose @('exec', '-T', 'postgres', 'createdb', '-U', 'mineassure', $rehearsalDatabase)
Invoke-Compose @('exec', '-T', 'postgres', 'pg_restore', '-U', 'mineassure', '-d', $rehearsalDatabase, '--exit-on-error', $containerArchive)

$tables = @('organisations', 'sites', 'users', 'contracts', 'contract_versions', 'work_records', 'invoices', 'invoice_lines', 'reconciliation_runs', 'approvals', 'export_batches', 'export_lines', 'audit_events')
foreach ($table in $tables) {
    $countQuery = 'SELECT count(*) FROM ' + $table
    $original = Invoke-Compose @('exec', '-T', 'postgres', 'psql', '-U', 'mineassure', '-d', 'mineassure', '-At', '-c', $countQuery)
    $restored = Invoke-Compose @('exec', '-T', 'postgres', 'psql', '-U', 'mineassure', '-d', $rehearsalDatabase, '-At', '-c', $countQuery)
    if (($original -join '').Trim() -ne ($restored -join '').Trim()) {
        throw "Count mismatch in $table. Pause mutations and repeat the rehearsal. Source database remains unchanged."
    }
    Write-Output ($table + ': ' + ($restored -join '').Trim() + ' rows restored')
}
$archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
Write-Output "Backup: $archivePath"
Write-Output "SHA256: $archiveHash"
Write-Output "Restore verified by pg_restore success and selected table counts: $rehearsalDatabase"
Write-Output 'The isolated restore database and archive are retained for inspection. No source data was deleted.'
