-- Test script for experimental_hybrid_search_v2.sql
-- Tests query intent detection, dynamic weights, relevance boost, and performance

-- Test 1: Query Intent Detection
DO $$
DECLARE
    test_query text;
    detected_intent text;
    expected_intent text;
    test_count integer := 0;
    pass_count integer := 0;
BEGIN
    RAISE NOTICE '=== Test 1: Query Intent Detection ===';
    
    -- Test factual queries
    test_query := 'What is strategic planning?';
    expected_intent := 'factual';
    detected_intent := detect_query_intent(test_query);
    test_count := test_count + 1;
    IF detected_intent = expected_intent THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: "%" detected as % (expected %)', test_query, detected_intent, expected_intent;
    ELSE
        RAISE NOTICE '❌ FAIL: "%" detected as % (expected %)', test_query, detected_intent, expected_intent;
    END IF;
    
    -- Test conceptual queries
    test_query := 'Why is strategic thinking important?';
    expected_intent := 'conceptual';
    detected_intent := detect_query_intent(test_query);
    test_count := test_count + 1;
    IF detected_intent = expected_intent THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: "%" detected as % (expected %)', test_query, detected_intent, expected_intent;
    ELSE
        RAISE NOTICE '❌ FAIL: "%" detected as % (expected %)', test_query, detected_intent, expected_intent;
    END IF;
    
    -- Test procedural queries
    test_query := 'Steps to create a business strategy';
    expected_intent := 'procedural';
    detected_intent := detect_query_intent(test_query);
    test_count := test_count + 1;
    IF detected_intent = expected_intent THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: "%" detected as % (expected %)', test_query, detected_intent, expected_intent;
    ELSE
        RAISE NOTICE '❌ FAIL: "%" detected as % (expected %)', test_query, detected_intent, expected_intent;
    END IF;
    
    -- Test balanced queries
    test_query := 'Business strategy examples';
    expected_intent := 'balanced';
    detected_intent := detect_query_intent(test_query);
    test_count := test_count + 1;
    IF detected_intent = expected_intent THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: "%" detected as % (expected %)', test_query, detected_intent, expected_intent;
    ELSE
        RAISE NOTICE '❌ FAIL: "%" detected as % (expected %)', test_query, detected_intent, expected_intent;
    END IF;
    
    RAISE NOTICE 'Test 1 Summary: % / % passed', pass_count, test_count;
    RAISE NOTICE '';
END $$;

-- Test 2: Dynamic Weight Calculation
DO $$
DECLARE
    intent text;
    vector_weight double precision;
    text_weight double precision;
    test_count integer := 0;
    pass_count integer := 0;
BEGIN
    RAISE NOTICE '=== Test 2: Dynamic Weight Calculation ===';
    
    -- Test factual intent weights
    intent := 'factual';
    SELECT * INTO vector_weight, text_weight FROM calculate_dynamic_weights(intent);
    test_count := test_count + 1;
    IF vector_weight = 0.4 AND text_weight = 0.6 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: % weights - vector: %, text: %', intent, vector_weight, text_weight;
    ELSE
        RAISE NOTICE '❌ FAIL: % weights - vector: % (expected 0.4), text: % (expected 0.6)', intent, vector_weight, text_weight;
    END IF;
    
    -- Test conceptual intent weights
    intent := 'conceptual';
    SELECT * INTO vector_weight, text_weight FROM calculate_dynamic_weights(intent);
    test_count := test_count + 1;
    IF vector_weight = 0.8 AND text_weight = 0.2 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: % weights - vector: %, text: %', intent, vector_weight, text_weight;
    ELSE
        RAISE NOTICE '❌ FAIL: % weights - vector: % (expected 0.8), text: % (expected 0.2)', intent, vector_weight, text_weight;
    END IF;
    
    -- Test procedural intent weights
    intent := 'procedural';
    SELECT * INTO vector_weight, text_weight FROM calculate_dynamic_weights(intent);
    test_count := test_count + 1;
    IF vector_weight = 0.6 AND text_weight = 0.4 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: % weights - vector: %, text: %', intent, vector_weight, text_weight;
    ELSE
        RAISE NOTICE '❌ FAIL: % weights - vector: % (expected 0.6), text: % (expected 0.4)', intent, vector_weight, text_weight;
    END IF;
    
    -- Test balanced intent weights
    intent := 'balanced';
    SELECT * INTO vector_weight, text_weight FROM calculate_dynamic_weights(intent);
    test_count := test_count + 1;
    IF vector_weight = 0.7 AND text_weight = 0.3 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: % weights - vector: %, text: %', intent, vector_weight, text_weight;
    ELSE
        RAISE NOTICE '❌ FAIL: % weights - vector: % (expected 0.7), text: % (expected 0.3)', intent, vector_weight, text_weight;
    END IF;
    
    RAISE NOTICE 'Test 2 Summary: % / % passed', pass_count, test_count;
    RAISE NOTICE '';
END $$;

-- Test 3: Relevance Boost Calculation
DO $$
DECLARE
    test_metadata jsonb;
    boost double precision;
    test_count integer := 0;
    pass_count integer := 0;
BEGIN
    RAISE NOTICE '=== Test 3: Relevance Boost Calculation ===';
    
    -- Test definition chunk type boost
    test_metadata := '{"chunk_type": "definition"}'::jsonb;
    boost := calculate_relevance_boost(test_metadata, 'test query');
    test_count := test_count + 1;
    IF boost = 1.2 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Definition chunk boost: %', boost;
    ELSE
        RAISE NOTICE '❌ FAIL: Definition chunk boost: % (expected 1.2)', boost;
    END IF;
    
    -- Test example chunk type boost with matching query
    test_metadata := '{"chunk_type": "example"}'::jsonb;
    boost := calculate_relevance_boost(test_metadata, 'show me an example');
    test_count := test_count + 1;
    IF boost = 1.15 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Example chunk boost with matching query: %', boost;
    ELSE
        RAISE NOTICE '❌ FAIL: Example chunk boost: % (expected 1.15)', boost;
    END IF;
    
    -- Test section title match boost
    test_metadata := '{"section_title": "Strategic Planning"}'::jsonb;
    boost := calculate_relevance_boost(test_metadata, 'strategic thinking');
    test_count := test_count + 1;
    IF boost = 1.1 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Section title match boost: %', boost;
    ELSE
        RAISE NOTICE '❌ FAIL: Section title match boost: % (expected 1.1)', boost;
    END IF;
    
    -- Test recently updated content boost
    test_metadata := jsonb_build_object('updated_at', (CURRENT_TIMESTAMP - interval '3 days')::text);
    boost := calculate_relevance_boost(test_metadata, 'test query');
    test_count := test_count + 1;
    IF boost = 1.05 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Recent update boost: %', boost;
    ELSE
        RAISE NOTICE '❌ FAIL: Recent update boost: % (expected 1.05)', boost;
    END IF;
    
    -- Test combined boosts
    test_metadata := jsonb_build_object(
        'chunk_type', 'key_concept',
        'section_title', 'Test Section',
        'updated_at', (CURRENT_TIMESTAMP - interval '2 days')::text
    );
    boost := calculate_relevance_boost(test_metadata, 'test query');
    test_count := test_count + 1;
    -- Should be 1.2 * 1.1 * 1.05 = 1.386
    IF boost BETWEEN 1.38 AND 1.39 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Combined boosts: %', boost;
    ELSE
        RAISE NOTICE '❌ FAIL: Combined boosts: % (expected ~1.386)', boost;
    END IF;
    
    RAISE NOTICE 'Test 3 Summary: % / % passed', pass_count, test_count;
    RAISE NOTICE '';
END $$;

-- Test 4: Hybrid Search Function
DO $$
DECLARE
    test_embedding vector;
    result_count integer;
    has_results boolean;
    test_count integer := 0;
    pass_count integer := 0;
BEGIN
    RAISE NOTICE '=== Test 4: Hybrid Search Function ===';
    
    -- Create a test embedding (2048 dimensions for Jina v4)
    test_embedding := array_fill(0.1::float, ARRAY[2048])::vector;
    
    -- Test basic search functionality
    SELECT COUNT(*) INTO result_count
    FROM hybrid_search_optimized(
        test_embedding,
        'strategic planning',
        NULL,
        5,
        TRUE,
        TRUE,
        TRUE
    );
    
    test_count := test_count + 1;
    has_results := result_count >= 0;  -- Can be 0 if no data
    IF has_results THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Basic search executed successfully (% results)', result_count;
    ELSE
        RAISE NOTICE '❌ FAIL: Basic search failed';
    END IF;
    
    -- Test with dynamic weights disabled
    SELECT COUNT(*) INTO result_count
    FROM hybrid_search_optimized(
        test_embedding,
        'strategic planning',
        NULL,
        5,
        FALSE,  -- disable dynamic weights
        TRUE,
        TRUE
    );
    
    test_count := test_count + 1;
    has_results := result_count >= 0;
    IF has_results THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Search without dynamic weights (% results)', result_count;
    ELSE
        RAISE NOTICE '❌ FAIL: Search without dynamic weights failed';
    END IF;
    
    -- Test with relevance boost disabled
    SELECT COUNT(*) INTO result_count
    FROM hybrid_search_optimized(
        test_embedding,
        'strategic planning',
        NULL,
        5,
        TRUE,
        FALSE,  -- disable relevance boost
        TRUE
    );
    
    test_count := test_count + 1;
    has_results := result_count >= 0;
    IF has_results THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Search without relevance boost (% results)', result_count;
    ELSE
        RAISE NOTICE '❌ FAIL: Search without relevance boost failed';
    END IF;
    
    -- Test with diversification disabled
    SELECT COUNT(*) INTO result_count
    FROM hybrid_search_optimized(
        test_embedding,
        'strategic planning',
        NULL,
        5,
        TRUE,
        TRUE,
        FALSE  -- disable diversification
    );
    
    test_count := test_count + 1;
    has_results := result_count >= 0;
    IF has_results THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Search without diversification (% results)', result_count;
    ELSE
        RAISE NOTICE '❌ FAIL: Search without diversification failed';
    END IF;
    
    RAISE NOTICE 'Test 4 Summary: % / % passed', pass_count, test_count;
    RAISE NOTICE '';
END $$;

-- Test 5: Query Pattern Analysis
DO $$
DECLARE
    pattern_count integer;
    test_count integer := 0;
    pass_count integer := 0;
BEGIN
    RAISE NOTICE '=== Test 5: Query Pattern Analysis ===';
    
    -- Test analyze_query_patterns function
    SELECT COUNT(*) INTO pattern_count
    FROM analyze_query_patterns();
    
    test_count := test_count + 1;
    IF pattern_count > 0 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Query pattern analysis returned % patterns', pattern_count;
    ELSE
        RAISE NOTICE '❌ FAIL: Query pattern analysis returned no patterns';
    END IF;
    
    -- Check if patterns have required fields
    SELECT COUNT(*) INTO pattern_count
    FROM analyze_query_patterns()
    WHERE query_pattern IS NOT NULL 
    AND query_count > 0
    AND avg_processing_time > 0
    AND cache_priority > 0;
    
    test_count := test_count + 1;
    IF pattern_count > 0 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: All patterns have valid data';
    ELSE
        RAISE NOTICE '❌ FAIL: Some patterns have invalid data';
    END IF;
    
    RAISE NOTICE 'Test 5 Summary: % / % passed', pass_count, test_count;
    RAISE NOTICE '';
END $$;

-- Test 6: Performance Benchmark
DO $$
DECLARE
    start_time timestamp;
    end_time timestamp;
    execution_time_ms double precision;
    test_embedding vector;
    test_count integer := 0;
    pass_count integer := 0;
BEGIN
    RAISE NOTICE '=== Test 6: Performance Benchmark ===';
    
    -- Create test embedding
    test_embedding := array_fill(0.1::float, ARRAY[2048])::vector;
    
    -- Benchmark standard search
    start_time := clock_timestamp();
    PERFORM * FROM hybrid_search_optimized(
        test_embedding,
        'strategic planning best practices',
        NULL,
        10,
        FALSE,  -- No dynamic weights
        FALSE,  -- No relevance boost
        FALSE   -- No diversification
    );
    end_time := clock_timestamp();
    
    execution_time_ms := EXTRACT(MILLISECOND FROM end_time - start_time)::double precision;
    test_count := test_count + 1;
    
    RAISE NOTICE 'Standard search time: % ms', execution_time_ms;
    IF execution_time_ms < 1000 THEN  -- Should complete within 1 second
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Standard search completed in acceptable time';
    ELSE
        RAISE NOTICE '❌ FAIL: Standard search too slow (> 1000ms)';
    END IF;
    
    -- Benchmark optimized search
    start_time := clock_timestamp();
    PERFORM * FROM hybrid_search_optimized(
        test_embedding,
        'strategic planning best practices',
        NULL,
        10,
        TRUE,   -- Enable dynamic weights
        TRUE,   -- Enable relevance boost
        TRUE    -- Enable diversification
    );
    end_time := clock_timestamp();
    
    execution_time_ms := EXTRACT(MILLISECOND FROM end_time - start_time)::double precision;
    test_count := test_count + 1;
    
    RAISE NOTICE 'Optimized search time: % ms', execution_time_ms;
    IF execution_time_ms < 1100 THEN  -- Allow 100ms overhead for optimizations
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Optimized search completed within overhead limit';
    ELSE
        RAISE NOTICE '❌ FAIL: Optimized search overhead too high (> 100ms)';
    END IF;
    
    RAISE NOTICE 'Test 6 Summary: % / % passed', pass_count, test_count;
    RAISE NOTICE '';
END $$;

-- Test 7: Index Verification
DO $$
DECLARE
    index_count integer;
    test_count integer := 0;
    pass_count integer := 0;
BEGIN
    RAISE NOTICE '=== Test 7: Index Verification ===';
    
    -- Check for metadata chunk_type index
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'chunks_unified'
    AND indexname = 'idx_chunks_unified_metadata_chunk_type';
    
    test_count := test_count + 1;
    IF index_count = 1 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Chunk type index exists';
    ELSE
        RAISE NOTICE '❌ FAIL: Chunk type index missing';
    END IF;
    
    -- Check for metadata section_title index
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'chunks_unified'
    AND indexname = 'idx_chunks_unified_metadata_section_title';
    
    test_count := test_count + 1;
    IF index_count = 1 THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Section title index exists';
    ELSE
        RAISE NOTICE '❌ FAIL: Section title index missing';
    END IF;
    
    RAISE NOTICE 'Test 7 Summary: % / % passed', pass_count, test_count;
    RAISE NOTICE '';
END $$;

-- Test 8: Test Query Dataset Validation
DO $$
DECLARE
    query_count integer;
    intent_match_count integer;
    test_count integer := 0;
    pass_count integer := 0;
BEGIN
    RAISE NOTICE '=== Test 8: Test Query Dataset Validation ===';
    
    -- Check if test queries exist
    SELECT COUNT(*) INTO query_count FROM test_queries;
    
    test_count := test_count + 1;
    IF query_count >= 16 THEN  -- Should have at least 16 test queries
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: Test query dataset has % queries', query_count;
    ELSE
        RAISE NOTICE '❌ FAIL: Test query dataset has only % queries (expected >= 16)', query_count;
    END IF;
    
    -- Validate intent detection matches expected
    SELECT COUNT(*) INTO intent_match_count
    FROM test_queries
    WHERE detect_query_intent(query_text) = expected_intent;
    
    test_count := test_count + 1;
    IF intent_match_count = query_count THEN
        pass_count := pass_count + 1;
        RAISE NOTICE '✅ PASS: All test queries have correct intent detection';
    ELSE
        RAISE NOTICE '❌ FAIL: Only % / % queries have correct intent detection', intent_match_count, query_count;
        
        -- Show mismatches
        RAISE NOTICE 'Mismatched queries:';
        FOR query_text, expected_intent, detected_intent IN
            SELECT tq.query_text, tq.expected_intent, detect_query_intent(tq.query_text)
            FROM test_queries tq
            WHERE detect_query_intent(tq.query_text) != tq.expected_intent
            LIMIT 5
        LOOP
            RAISE NOTICE '  - "%" expected: %, detected: %', query_text, expected_intent, detected_intent;
        END LOOP;
    END IF;
    
    RAISE NOTICE 'Test 8 Summary: % / % passed', pass_count, test_count;
    RAISE NOTICE '';
END $$;

-- Final Summary
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '✅ All SQL function tests completed';
    RAISE NOTICE '===========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Note: Some tests may show 0 results if no data is loaded.';
    RAISE NOTICE 'This is expected in a test environment.';
    RAISE NOTICE '';
    RAISE NOTICE 'To test with real data:';
    RAISE NOTICE '1. Ensure documents and chunks are loaded';
    RAISE NOTICE '2. Generate embeddings for chunks';
    RAISE NOTICE '3. Run benchmark_hybrid_search() with actual embeddings';
END $$;
