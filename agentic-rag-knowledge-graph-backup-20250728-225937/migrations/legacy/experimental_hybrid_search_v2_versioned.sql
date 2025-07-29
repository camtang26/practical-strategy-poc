-- Optimized Hybrid Search with Query Intent Detection and Dynamic Weighting
-- WITH POSTGRESQL VERSION CHECKING

-- Version check and requirements validation
DO $$
DECLARE
    pg_version_num integer;
    pg_version_text text;
    has_pgvector boolean;
    has_uuid_ossp boolean;
BEGIN
    -- Get PostgreSQL version
    SELECT current_setting('server_version_num')::integer INTO pg_version_num;
    SELECT current_setting('server_version') INTO pg_version_text;
    
    RAISE NOTICE 'PostgreSQL version detected: % (version number: %)', pg_version_text, pg_version_num;
    
    -- Check minimum PostgreSQL version (11.0 = 110000)
    IF pg_version_num < 110000 THEN
        RAISE EXCEPTION 'PostgreSQL version % is not supported. Minimum required version is 11.0. ' ||
                        'This migration uses features like pgvector that require PostgreSQL 11+.',
                        pg_version_text;
    END IF;
    
    -- Check for pgvector extension
    SELECT EXISTS (
        SELECT 1 FROM pg_available_extensions 
        WHERE name = 'vector'
    ) INTO has_pgvector;
    
    IF NOT has_pgvector THEN
        RAISE EXCEPTION 'pgvector extension is not available. ' ||
                        'Please install pgvector extension first: ' ||
                        'https://github.com/pgvector/pgvector#installation';
    END IF;
    
    -- Check if pgvector is installed
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'pgvector extension is available but not installed. Installing now...';
        CREATE EXTENSION IF NOT EXISTS vector;
    END IF;
    
    -- Check for uuid-ossp extension
    SELECT EXISTS (
        SELECT 1 FROM pg_available_extensions 
        WHERE name = 'uuid-ossp'
    ) INTO has_uuid_ossp;
    
    IF NOT has_uuid_ossp THEN
        RAISE WARNING 'uuid-ossp extension is not available. ' ||
                      'UUID generation functions may not work properly.';
    ELSE
        -- Ensure uuid-ossp is installed
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    END IF;
    
    -- Version-specific feature checks
    IF pg_version_num >= 120000 THEN
        RAISE NOTICE 'PostgreSQL 12+ detected. All advanced features available.';
    ELSIF pg_version_num >= 110000 THEN
        RAISE NOTICE 'PostgreSQL 11 detected. Core features available, some optimizations may be limited.';
    END IF;
    
    -- Check for required table structures
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chunks_unified') THEN
        RAISE EXCEPTION 'Required table "chunks_unified" does not exist. ' ||
                        'Please run the base schema migration first.';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents') THEN
        RAISE EXCEPTION 'Required table "documents" does not exist. ' ||
                        'Please run the base schema migration first.';
    END IF;
    
    -- Check for required columns
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chunks_unified' AND column_name = 'embedding'
    ) THEN
        RAISE EXCEPTION 'Required column "embedding" does not exist in chunks_unified table.';
    END IF;
    
    RAISE NOTICE 'All version and dependency checks passed. Proceeding with migration...';
END $$;

-- Helper function to detect query intent
CREATE OR REPLACE FUNCTION detect_query_intent(query_text text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    factual_keywords text[] := ARRAY['what is', 'define', 'list', 'when', 'where', 'who', 'how many', 'how much'];
    conceptual_keywords text[] := ARRAY['why', 'how to', 'explain', 'understand', 'strategy', 'approach', 'best practice', 'principle'];
    procedural_keywords text[] := ARRAY['steps', 'process', 'procedure', 'implement', 'create', 'build', 'develop'];
    query_lower text;
    keyword text;
BEGIN
    query_lower := lower(query_text);
    
    -- Check for factual intent
    FOREACH keyword IN ARRAY factual_keywords LOOP
        IF query_lower LIKE '%' || keyword || '%' THEN
            RETURN 'factual';
        END IF;
    END LOOP;
    
    -- Check for procedural intent
    FOREACH keyword IN ARRAY procedural_keywords LOOP
        IF query_lower LIKE '%' || keyword || '%' THEN
            RETURN 'procedural';
        END IF;
    END LOOP;
    
    -- Check for conceptual intent
    FOREACH keyword IN ARRAY conceptual_keywords LOOP
        IF query_lower LIKE '%' || keyword || '%' THEN
            RETURN 'conceptual';
        END IF;
    END LOOP;
    
    -- Default to balanced
    RETURN 'balanced';
END;
$$;

-- Function to calculate dynamic weights based on query intent
CREATE OR REPLACE FUNCTION calculate_dynamic_weights(query_intent text, OUT vector_weight double precision, OUT text_weight double precision)
LANGUAGE plpgsql
AS $$
BEGIN
    CASE query_intent
        WHEN 'factual' THEN
            -- Factual queries benefit more from text search
            vector_weight := 0.4;
            text_weight := 0.6;
        WHEN 'conceptual' THEN
            -- Conceptual queries benefit more from semantic search
            vector_weight := 0.8;
            text_weight := 0.2;
        WHEN 'procedural' THEN
            -- Procedural queries need balanced approach
            vector_weight := 0.6;
            text_weight := 0.4;
        ELSE
            -- Default balanced weights
            vector_weight := 0.7;
            text_weight := 0.3;
    END CASE;
END;
$$;

-- Function to boost relevance for important chunks
CREATE OR REPLACE FUNCTION calculate_relevance_boost(metadata jsonb, query_text text)
RETURNS double precision
LANGUAGE plpgsql
AS $$
DECLARE
    boost double precision := 1.0;
    chunk_type text;
    section_title text;
BEGIN
    -- Extract metadata fields
    chunk_type := metadata->>'chunk_type';
    section_title := metadata->>'section_title';
    
    -- Boost based on chunk type
    IF chunk_type IN ('definition', 'key_concept', 'principle') THEN
        boost := boost * 1.2;
    ELSIF chunk_type = 'example' AND position('example' IN lower(query_text)) > 0 THEN
        boost := boost * 1.15;
    ELSIF chunk_type = 'summary' THEN
        boost := boost * 1.1;
    END IF;
    
    -- Boost if section title matches query terms
    IF section_title IS NOT NULL AND lower(section_title) LIKE '%' || lower(split_part(query_text, ' ', 1)) || '%' THEN
        boost := boost * 1.1;
    END IF;
    
    -- Boost recently updated content
    IF metadata->>'updated_at' IS NOT NULL AND 
       (CURRENT_TIMESTAMP - (metadata->>'updated_at')::timestamp) < interval '7 days' THEN
        boost := boost * 1.05;
    END IF;
    
    RETURN boost;
END;
$$;

-- Optimized Hybrid Search Function
CREATE OR REPLACE FUNCTION hybrid_search_optimized(
    query_embedding vector,
    query_text text,
    embedding_provider_filter TEXT DEFAULT NULL,
    match_count INTEGER DEFAULT 10,
    enable_dynamic_weights BOOLEAN DEFAULT TRUE,
    enable_relevance_boost BOOLEAN DEFAULT TRUE,
    enable_diversification BOOLEAN DEFAULT TRUE
)
RETURNS TABLE(
    chunk_id uuid,
    document_id uuid,
    content text,
    combined_score double precision,
    vector_similarity double precision,
    text_similarity double precision,
    metadata jsonb,
    document_title text,
    document_source text,
    embedding_model text,
    embedding_provider text,
    query_intent text,
    relevance_boost double precision
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_query_intent text;
    v_vector_weight double precision;
    v_text_weight double precision;
BEGIN
    -- Detect query intent
    v_query_intent := CASE 
        WHEN enable_dynamic_weights THEN detect_query_intent(query_text)
        ELSE 'balanced'
    END;
    
    -- Calculate dynamic weights
    IF enable_dynamic_weights THEN
        SELECT * INTO v_vector_weight, v_text_weight 
        FROM calculate_dynamic_weights(v_query_intent);
    ELSE
        v_vector_weight := 0.7;
        v_text_weight := 0.3;
    END IF;
    
    RETURN QUERY
    WITH vector_results AS (
        SELECT 
            c.id AS chunk_id,
            c.document_id,
            c.content,
            1 - (c.embedding <=> query_embedding) AS vector_sim,
            c.metadata,
            d.title AS doc_title,
            d.source AS doc_source,
            c.embedding_model,
            c.embedding_provider,
            c.chunk_index
        FROM chunks_unified c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
        AND (embedding_provider_filter IS NULL OR c.embedding_provider = embedding_provider_filter)
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count * 3  -- Get extra results for diversification
    ),
    text_results AS (
        SELECT 
            c.id AS chunk_id,
            c.document_id,
            c.content,
            ts_rank_cd(
                to_tsvector('english', c.content), 
                plainto_tsquery('english', query_text),
                32  -- Enable all normalization options
            )::double precision AS text_sim,
            c.metadata,
            d.title AS doc_title,
            d.source AS doc_source,
            c.embedding_model,
            c.embedding_provider,
            c.chunk_index
        FROM chunks_unified c
        JOIN documents d ON c.document_id = d.id
        WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', query_text)
        AND (embedding_provider_filter IS NULL OR c.embedding_provider = embedding_provider_filter)
        ORDER BY text_sim DESC
        LIMIT match_count * 3  -- Get extra results for diversification
    ),
    combined_results AS (
        SELECT 
            COALESCE(v.chunk_id, t.chunk_id) AS chunk_id,
            COALESCE(v.document_id, t.document_id) AS document_id,
            COALESCE(v.content, t.content) AS content,
            COALESCE(v.vector_sim, 0) AS vector_sim,
            COALESCE(t.text_sim, 0) AS text_sim,
            COALESCE(v.metadata, t.metadata) AS metadata,
            COALESCE(v.doc_title, t.doc_title) AS document_title,
            COALESCE(v.doc_source, t.doc_source) AS document_source,
            COALESCE(v.embedding_model, t.embedding_model) AS embedding_model,
            COALESCE(v.embedding_provider, t.embedding_provider) AS embedding_provider,
            COALESCE(v.chunk_index, t.chunk_index) AS chunk_index,
            CASE 
                WHEN enable_relevance_boost THEN 
                    calculate_relevance_boost(COALESCE(v.metadata, t.metadata), query_text)
                ELSE 1.0 
            END AS relevance_boost
        FROM vector_results v
        FULL OUTER JOIN text_results t ON v.chunk_id = t.chunk_id
    ),
    scored_results AS (
        SELECT 
            *,
            ((vector_sim * v_vector_weight + text_sim * v_text_weight) * relevance_boost) AS final_score,
            v_query_intent AS query_intent_value
        FROM combined_results
    ),
    diversified_results AS (
        SELECT DISTINCT ON (
            CASE 
                WHEN enable_diversification THEN 
                    -- Group by document and nearby chunks to avoid redundancy
                    (document_id::text || '_' || (chunk_index / 3)::text)
                ELSE 
                    chunk_id::text
            END
        )
        chunk_id,
        document_id,
        content,
        final_score AS combined_score,
        vector_sim AS vector_similarity,
        text_sim AS text_similarity,
        metadata,
        document_title,
        document_source,
        embedding_model,
        embedding_provider,
        query_intent_value AS query_intent,
        relevance_boost
        FROM scored_results
        ORDER BY 
            CASE 
                WHEN enable_diversification THEN 
                    (document_id::text || '_' || (chunk_index / 3)::text)
                ELSE 
                    chunk_id::text
            END,
            final_score DESC
    )
    SELECT * FROM diversified_results
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$;

-- Create indexes with version-aware optimizations
DO $$
DECLARE
    pg_version_num integer;
BEGIN
    SELECT current_setting('server_version_num')::integer INTO pg_version_num;
    
    -- Create basic indexes (all versions)
    CREATE INDEX IF NOT EXISTS idx_chunks_unified_metadata_chunk_type 
    ON chunks_unified ((metadata->>'chunk_type'));

    CREATE INDEX IF NOT EXISTS idx_chunks_unified_metadata_section_title 
    ON chunks_unified ((metadata->>'section_title'));
    
    -- PostgreSQL 12+ can use more advanced index options
    IF pg_version_num >= 120000 THEN
        -- Create covering indexes for better performance
        DROP INDEX IF EXISTS idx_chunks_unified_embedding_provider;
        CREATE INDEX idx_chunks_unified_embedding_provider 
        ON chunks_unified (embedding_provider) 
        INCLUDE (id, document_id, content, embedding_model);
        
        RAISE NOTICE 'Created covering indexes (PostgreSQL 12+ feature)';
    ELSE
        -- Create standard indexes for older versions
        CREATE INDEX IF NOT EXISTS idx_chunks_unified_embedding_provider 
        ON chunks_unified (embedding_provider);
        
        RAISE NOTICE 'Created standard indexes (PostgreSQL 11 compatible)';
    END IF;
END $$;

-- Function to analyze query patterns for caching
CREATE OR REPLACE FUNCTION analyze_query_patterns()
RETURNS TABLE(
    query_pattern text,
    query_count bigint,
    avg_processing_time double precision,
    cache_priority integer
)
LANGUAGE plpgsql
AS $$
BEGIN
    -- This would need a query_logs table to be implemented
    -- For now, return sample patterns that should be cached
    RETURN QUERY
    SELECT 
        pattern,
        count,
        avg_time,
        priority
    FROM (VALUES
        ('what is strategic planning', 150::bigint, 2.5::double precision, 1::integer),
        ('how to create a strategy', 120::bigint, 3.2::double precision, 2::integer),
        ('define business strategy', 100::bigint, 2.1::double precision, 3::integer),
        ('strategic thinking principles', 90::bigint, 3.5::double precision, 4::integer),
        ('strategy implementation steps', 85::bigint, 2.8::double precision, 5::integer)
    ) AS patterns(pattern, count, avg_time, priority);
END;
$$;

-- Test query dataset for optimization
CREATE TABLE IF NOT EXISTS test_queries (
    id SERIAL PRIMARY KEY,
    query_text text NOT NULL,
    expected_intent text,
    optimal_vector_weight double precision,
    optimal_text_weight double precision,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample test queries with conflict handling
INSERT INTO test_queries (query_text, expected_intent, optimal_vector_weight, optimal_text_weight) VALUES
-- Factual queries
('What is the definition of strategic planning?', 'factual', 0.4, 0.6),
('List the key components of a business strategy', 'factual', 0.4, 0.6),
('When should a company update its strategy?', 'factual', 0.4, 0.6),
('Who are the stakeholders in strategic planning?', 'factual', 0.4, 0.6),
-- Conceptual queries  
('Why is strategic thinking important for business success?', 'conceptual', 0.8, 0.2),
('Explain the relationship between vision and strategy', 'conceptual', 0.8, 0.2),
('How does competitive advantage relate to strategy?', 'conceptual', 0.8, 0.2),
('What are the principles of effective strategic leadership?', 'conceptual', 0.8, 0.2),
-- Procedural queries
('What are the steps to create a strategic plan?', 'procedural', 0.6, 0.4),
('How to implement a new business strategy?', 'procedural', 0.6, 0.4),
('Process for conducting strategic analysis', 'procedural', 0.6, 0.4),
('How to develop strategic objectives and KPIs?', 'procedural', 0.6, 0.4),
-- Balanced queries
('Strategic planning best practices for startups', 'balanced', 0.7, 0.3),
('Examples of successful business strategies', 'balanced', 0.7, 0.3),
('Common strategic planning mistakes to avoid', 'balanced', 0.7, 0.3),
('How to align strategy with organizational culture', 'balanced', 0.7, 0.3)
ON CONFLICT DO NOTHING;

-- Function to benchmark search performance with version awareness
CREATE OR REPLACE FUNCTION benchmark_hybrid_search(
    test_query_id integer,
    embedding_vector vector
)
RETURNS TABLE(
    query_text text,
    execution_time_ms double precision,
    result_count integer,
    top_score double precision,
    pg_version text
)
LANGUAGE plpgsql
AS $$
DECLARE
    start_time timestamp;
    end_time timestamp;
    v_query_text text;
    v_result_count integer;
    v_top_score double precision;
    v_pg_version text;
BEGIN
    -- Get PostgreSQL version
    SELECT current_setting('server_version') INTO v_pg_version;
    
    -- Get query text
    SELECT tq.query_text INTO v_query_text
    FROM test_queries tq
    WHERE tq.id = test_query_id;
    
    -- Measure execution time
    start_time := clock_timestamp();
    
    SELECT COUNT(*), MAX(combined_score) INTO v_result_count, v_top_score
    FROM hybrid_search_optimized(
        embedding_vector,
        v_query_text,
        NULL,
        10,
        TRUE,
        TRUE,
        TRUE
    );
    
    end_time := clock_timestamp();
    
    RETURN QUERY
    SELECT 
        v_query_text,
        EXTRACT(MILLISECOND FROM end_time - start_time)::double precision,
        v_result_count,
        v_top_score,
        v_pg_version;
END;
$$;

-- Final validation
DO $$
BEGIN
    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE 'Created functions: detect_query_intent, calculate_dynamic_weights, calculate_relevance_boost, hybrid_search_optimized';
    RAISE NOTICE 'Created indexes for improved performance';
    RAISE NOTICE 'Created test infrastructure for query optimization';
END $$;
