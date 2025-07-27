-- Experimental Hybrid Search v2 - Core Functions Only
-- Version without vector index due to 2048 > 2000 dimension limit

-- Function 1: Detect Query Intent
CREATE OR REPLACE FUNCTION detect_query_intent(
    query_text text
) RETURNS TABLE (
    intent_type text,
    factual_score float,
    conceptual_score float,
    procedural_score float
) AS $$
DECLARE
    lower_query text;
    word_count int;
BEGIN
    lower_query := lower(query_text);
    word_count := array_length(string_to_array(query_text, ' '), 1);
    
    -- Calculate scores based on linguistic patterns
    factual_score := 0.0;
    conceptual_score := 0.0;
    procedural_score := 0.0;
    
    -- Factual indicators
    IF lower_query ~ '\m(what|when|where|who|which|define|meaning)\M' THEN
        factual_score := factual_score + 0.4;
    END IF;
    IF lower_query ~ '\m(is|are|was|were)\M' AND word_count < 10 THEN
        factual_score := factual_score + 0.3;
    END IF;
    IF lower_query ~ '\m(definition|fact|date|number|statistic)\M' THEN
        factual_score := factual_score + 0.3;
    END IF;
    
    -- Conceptual indicators
    IF lower_query ~ '\m(how|why|explain|understand|relate|impact|affect)\M' THEN
        conceptual_score := conceptual_score + 0.4;
    END IF;
    IF lower_query ~ '\m(concept|theory|principle|relationship|connection)\M' THEN
        conceptual_score := conceptual_score + 0.3;
    END IF;
    IF word_count > 15 THEN
        conceptual_score := conceptual_score + 0.2;
    END IF;
    
    -- Procedural indicators
    IF lower_query ~ '\m(how to|steps|process|implement|create|build)\M' THEN
        procedural_score := procedural_score + 0.5;
    END IF;
    IF lower_query ~ '\m(guide|tutorial|instruction|procedure|method)\M' THEN
        procedural_score := procedural_score + 0.3;
    END IF;
    IF lower_query ~ '\m(first|then|next|finally|begin|start)\M' THEN
        procedural_score := procedural_score + 0.2;
    END IF;
    
    -- Normalize scores
    DECLARE
        total_score float;
    BEGIN
        total_score := factual_score + conceptual_score + procedural_score;
        IF total_score > 0 THEN
            factual_score := factual_score / total_score;
            conceptual_score := conceptual_score / total_score;
            procedural_score := procedural_score / total_score;
        ELSE
            -- Default to balanced if no clear indicators
            factual_score := 0.33;
            conceptual_score := 0.34;
            procedural_score := 0.33;
        END IF;
    END;
    
    -- Determine primary intent
    IF factual_score >= conceptual_score AND factual_score >= procedural_score THEN
        intent_type := 'factual';
    ELSIF conceptual_score >= procedural_score THEN
        intent_type := 'conceptual';
    ELSIF procedural_score > 0.5 THEN
        intent_type := 'procedural';
    ELSE
        intent_type := 'balanced';
    END IF;
    
    RETURN QUERY SELECT intent_type, factual_score, conceptual_score, procedural_score;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 2: Calculate Dynamic Weights
CREATE OR REPLACE FUNCTION calculate_dynamic_weights(
    intent text
) RETURNS TABLE (
    semantic_weight float,
    keyword_weight float,
    proximity_weight float
) AS $$
BEGIN
    CASE intent
        WHEN 'factual' THEN
            -- Factual queries: high keyword weight for exact matches
            semantic_weight := 0.3;
            keyword_weight := 0.5;
            proximity_weight := 0.2;
        WHEN 'conceptual' THEN
            -- Conceptual queries: balanced semantic and keyword
            semantic_weight := 0.5;
            keyword_weight := 0.3;
            proximity_weight := 0.2;
        WHEN 'procedural' THEN
            -- Procedural queries: high proximity for step sequences
            semantic_weight := 0.4;
            keyword_weight := 0.2;
            proximity_weight := 0.4;
        ELSE
            -- Balanced/default weights
            semantic_weight := 0.4;
            keyword_weight := 0.3;
            proximity_weight := 0.3;
    END CASE;
    
    RETURN QUERY SELECT semantic_weight, keyword_weight, proximity_weight;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function 3: Main Hybrid Search Function (simplified without index)
CREATE OR REPLACE FUNCTION experimental_hybrid_search_v2(
    query_text text,
    query_embedding vector,
    match_count int DEFAULT 5,
    similarity_threshold float DEFAULT 0.3
) RETURNS TABLE (
    chunk_id uuid,
    document_id uuid,
    content text,
    source text,
    semantic_score float,
    keyword_score float, 
    proximity_score float,
    final_score float,
    metadata jsonb
) AS $$
DECLARE
    query_intent record;
    weights record;
    query_terms text[];
BEGIN
    -- Detect query intent
    SELECT * INTO query_intent FROM detect_query_intent(query_text);
    
    -- Get dynamic weights based on intent
    SELECT * INTO weights FROM calculate_dynamic_weights(query_intent.intent_type);
    
    -- Extract query terms for keyword matching
    query_terms := string_to_array(lower(query_text), ' ');
    
    RETURN QUERY
    WITH 
    -- Semantic similarity search using pgvector (without index for now)
    semantic_matches AS (
        SELECT 
            c.id,
            c.document_id,
            c.content,
            1 - (c.embedding <=> query_embedding) as similarity
        FROM chunks_jina c
        WHERE c.embedding IS NOT NULL
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count * 3  -- Get more candidates for re-ranking
    ),
    -- Keyword matching
    keyword_matches AS (
        SELECT 
            c.id,
            c.document_id,
            ts_rank_cd(
                to_tsvector('english', c.content),
                plainto_tsquery('english', query_text),
                32  -- Cover density ranking
            ) as keyword_rank
        FROM chunks_jina c
        WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', query_text)
    ),
    -- Calculate proximity scores (simplified)
    proximity_calc AS (
        SELECT 
            sm.id,
            sm.document_id,
            sm.content,
            sm.similarity,
            COALESCE(km.keyword_rank, 0) as keyword_rank,
            -- Simplified proximity score
            CASE 
                WHEN km.keyword_rank > 0 THEN 0.5
                ELSE 0.1
            END as proximity
        FROM semantic_matches sm
        LEFT JOIN keyword_matches km ON sm.id = km.id
    ),
    -- Combine scores with dynamic weights
    scored_results AS (
        SELECT
            pc.id,
            pc.document_id,
            pc.content,
            d.source,
            pc.similarity as semantic_score,
            pc.keyword_rank as keyword_score,
            pc.proximity as proximity_score,
            -- Apply dynamic weights
            (weights.semantic_weight * pc.similarity +
             weights.keyword_weight * pc.keyword_rank +
             weights.proximity_weight * pc.proximity) as final_score,
            COALESCE(c.metadata, '{}'::jsonb) as metadata
        FROM proximity_calc pc
        JOIN chunks_jina c ON pc.id = c.id
        JOIN documents d ON pc.document_id = d.id
        WHERE pc.similarity >= similarity_threshold
    )
    -- Return results ordered by final score
    SELECT 
        sr.id as chunk_id,
        sr.document_id,
        sr.content,
        sr.source,
        sr.semantic_score,
        sr.keyword_score,
        sr.proximity_score,
        sr.final_score,
        sr.metadata
    FROM scored_results sr
    ORDER BY sr.final_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql STABLE;

-- Create text search index only (this should work)
CREATE INDEX IF NOT EXISTS idx_chunks_jina_content_gin 
ON chunks_jina USING gin(to_tsvector('english', content));

-- Add helpful comments
COMMENT ON FUNCTION detect_query_intent IS 'Analyzes query text to determine search intent type';
COMMENT ON FUNCTION calculate_dynamic_weights IS 'Returns optimized weights based on query intent';
COMMENT ON FUNCTION experimental_hybrid_search_v2 IS 'Advanced hybrid search with query intent detection and dynamic weighting (without vector index due to dimension limit)';
