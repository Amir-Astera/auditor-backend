-- Migration: Add Full-Text Search to file_chunks table
-- Run this migration to enable PostgreSQL FTS for hybrid search

-- 1. Add tsvector column for search
ALTER TABLE file_chunks 
ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- 2. Create GIN index for fast FTS queries
CREATE INDEX IF NOT EXISTS idx_file_chunks_search_vector 
ON file_chunks USING GIN(search_vector);

-- 3. Create function to update search vector
CREATE OR REPLACE FUNCTION file_chunks_search_vector_update() 
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('russian', COALESCE(NEW.text, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.text, '')), 'B');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- 4. Create trigger for auto-update on insert/update
DROP TRIGGER IF EXISTS file_chunks_search_vector_trigger ON file_chunks;
CREATE TRIGGER file_chunks_search_vector_trigger
BEFORE INSERT OR UPDATE ON file_chunks
FOR EACH ROW EXECUTE FUNCTION file_chunks_search_vector_update();

-- 5. Update existing rows with search vectors
UPDATE file_chunks 
SET search_vector = 
    setweight(to_tsvector('russian', COALESCE(text, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(text, '')), 'B')
WHERE search_vector IS NULL;

-- 6. Add index on file_id for faster joins
CREATE INDEX IF NOT EXISTS idx_file_chunks_file_id ON file_chunks(file_id);

-- 7. Add composite index for common filter patterns
CREATE INDEX IF NOT EXISTS idx_stored_files_scope_customer 
ON stored_files(scope, customer_id);
