#!/bin/bash
# Run database migrations for Universal Face System
# Usage: ./run_migrations.sh

set -e

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable not set"
    echo "Example: export DATABASE_URL='postgresql+asyncpg://user:pass@localhost/dbname'"
    exit 1
fi

# Extract connection parameters from DATABASE_URL
# Expected format: postgresql+asyncpg://user:password@host:port/dbname

echo "🔄 Running Universal Face System database migrations..."

# Convert asyncpg URL to psql URL for running SQL scripts
DB_URL=$(echo "$DATABASE_URL" | sed 's/+asyncpg//')

# Run migrations
echo "📋 Migration 1: Adding pgvector HNSW indexes..."
psql "$DB_URL" -f migrations/001_add_pgvector_hnsw_index.sql

if [ $? -eq 0 ]; then
    echo "✅ All migrations completed successfully!"
    echo ""
    echo "📊 To verify indexes were created, run:"
    echo "   psql $DB_URL -c \"SELECT indexname FROM pg_indexes WHERE tablename='registered_faces';\""
else
    echo "❌ Migration failed!"
    exit 1
fi
