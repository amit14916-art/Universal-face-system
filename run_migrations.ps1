# Run database migrations for Universal Face System (Windows PowerShell)
# Usage: .\run_migrations.ps1

param(
    [string]$DatabaseUrl = $env:DATABASE_URL
)

if ([string]::IsNullOrEmpty($DatabaseUrl)) {
    Write-Host "ERROR: DATABASE_URL environment variable not set" -ForegroundColor Red
    Write-Host "Example: `$env:DATABASE_URL='postgresql+asyncpg://user:pass@localhost/dbname'"
    exit 1
}

Write-Host "`n🔄 Running Universal Face System database migrations..." -ForegroundColor Cyan

# Convert asyncpg URL to psql URL for running SQL scripts
$DbUrl = $DatabaseUrl -replace '\+asyncpg', ''

# Check if psql is available
try {
    $psqlVersion = psql --version 2>$null
} catch {
    Write-Host "ERROR: psql not found. Please install PostgreSQL client tools." -ForegroundColor Red
    exit 1
}

Write-Host "📋 Migration 1: Adding pgvector HNSW indexes..." -ForegroundColor Yellow

# Run migration
& psql "$DbUrl" -f "migrations\001_add_pgvector_hnsw_index.sql" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ All migrations completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 To verify indexes were created, run:" -ForegroundColor Green
    Write-Host "   psql `"$DbUrl`" -c ""SELECT indexname FROM pg_indexes WHERE tablename='registered_faces';""" -ForegroundColor Gray
} else {
    Write-Host "`n❌ Migration failed!" -ForegroundColor Red
    exit 1
}
