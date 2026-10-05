
$ErrorActionPreference = "Stop"

# 1. Configuration
$backupDirectory = "$env:USERPROFILE\Documents\insurance_backups"
$pgDump = "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
$retentionDays = 14

# 2. Ensure the backup directory and pg_dump exist
if (-not (Test-Path $backupDirectory)) {
    New-Item -ItemType Directory -Path $backupDirectory -Force |
        Out-Null
}

if (-not (Test-Path $pgDump)) {
    throw "pg_dump.exe was not found at: $pgDump"
}

# 3. Create a timestamped backup
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $backupDirectory `
    "insurance_claims_db_$timestamp.backup"

& $pgDump `
    --host=localhost `
    --port=5432 `
    --username=postgres `
    --dbname=insurance_claims_db `
    --format=custom `
    --no-password `
    --file="$backupFile"

# 4. Verify the backup command succeeded
if ($LASTEXITCODE -ne 0) {
    Remove-Item $backupFile -ErrorAction SilentlyContinue
    throw "Database backup failed with exit code $LASTEXITCODE"
}

# 5. Verify the backup file exists and is not empty
if (-not (Test-Path $backupFile) -or
    (Get-Item $backupFile).Length -eq 0) {
    throw "Backup file is missing or empty."
}

Write-Output "Backup completed successfully."
Get-Item $backupFile |
    Select-Object FullName, Length, LastWriteTime

# 6. Cleanup: identify backups older than 14 days
$cutoffDate = (Get-Date).AddDays(-$retentionDays)

$oldBackups = @(
    Get-ChildItem -Path $backupDirectory `
        -Filter "insurance_claims_db_*.backup" `
        -File |
    Where-Object {
        $_.LastWriteTime -lt $cutoffDate -and
        $_.FullName -ne $backupFile
    }
)

# 7. Delete only old backups, after successful backup creation
foreach ($oldBackup in $oldBackups) {
    Remove-Item -LiteralPath $oldBackup.FullName -Force
    Write-Output "Deleted expired backup: $($oldBackup.Name)"
}

Write-Output "Backup retention cleanup completed."
Write-Output "Retention period: $retentionDays days."