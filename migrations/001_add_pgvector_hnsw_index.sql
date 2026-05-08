-- Migration: Add pgvector HNSW indexes for fast face similarity search
-- This migration adds HNSW indexes on face embeddings for O(log n) query time
-- instead of O(n) linear scan

-- Add HNSW index for all faces
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_face_encoding_hnsw 
ON registered_faces USING hnsw (face_encoding l2_ops)
WITH (m=16, ef_construction=200);

-- Add partial index for faster queries on active non-blacklisted users
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_face_encoding_active 
ON registered_faces USING hnsw (face_encoding l2_ops)
WHERE is_active = true AND is_blacklisted = false;

-- Add indexes on foreign keys for better join performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_attendance_owner_id 
ON attendance_logs(owner_id) 
WHERE timestamp >= CURRENT_DATE - INTERVAL '90 days';

-- Gather statistics for query planner
ANALYZE registered_faces;
ANALYZE attendance_logs;

-- Display index info
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE schemaname = 'public' 
  AND tablename IN ('registered_faces', 'attendance_logs')
ORDER BY indexname;
