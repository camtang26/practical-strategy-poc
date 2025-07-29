"""
Test SQL functions on actual database.
"""

import asyncio
import asyncpg
import os
import time
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


async def test_sql_functions():
    """Test hybrid search SQL functions on live database."""
    conn = None
    try:
        logger.info("Connecting to database...")
        conn = await asyncpg.connect(DATABASE_URL)
        logger.info("✓ Connected to database")
        
        # Check if functions exist
        logger.info("\n=== Checking SQL Functions ===")
        functions = [
            'detect_query_intent',
            'calculate_dynamic_weights', 
            'experimental_hybrid_search_v2'
        ]
        
        for func_name in functions:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc p 
                    JOIN pg_namespace n ON p.pronamespace = n.oid 
                    WHERE n.nspname = 'public' AND p.proname = $1
                )
            """, func_name)
            
            if result:
                logger.info(f"✓ Function {func_name} exists")
            else:
                logger.error(f"✗ Function {func_name} NOT FOUND")
        
        # Test 1: Query Intent Detection
        logger.info("\n=== Testing Query Intent Detection ===")
        test_queries = [
            ("What is strategic planning?", "factual"),
            ("How does organizational culture impact strategy?", "conceptual"),
            ("What are the steps to implement a balanced scorecard?", "procedural"),
            ("Explain strategy implementation best practices", "balanced")
        ]
        
        for query, expected_type in test_queries:
            start = time.time()
            result = await conn.fetchrow(
                "SELECT * FROM detect_query_intent($1)", 
                query
            )
            duration = (time.time() - start) * 1000
            
            logger.info(f"Query: '{query[:50]}...'")
            logger.info(f"  Intent: {result['intent_type']} (expected: {expected_type})")
            logger.info(f"  Scores: factual={result['factual_score']:.2f}, "
                       f"conceptual={result['conceptual_score']:.2f}, "
                       f"procedural={result['procedural_score']:.2f}")
            logger.info(f"  Duration: {duration:.1f}ms")
        
        # Test 2: Dynamic Weight Calculation
        logger.info("\n=== Testing Dynamic Weight Calculation ===")
        intents = ['factual', 'conceptual', 'procedural', 'balanced']
        
        for intent in intents:
            start = time.time()
            result = await conn.fetchrow(
                "SELECT * FROM calculate_dynamic_weights($1::text)",
                intent
            )
            duration = (time.time() - start) * 1000
            
            logger.info(f"Intent: {intent}")
            logger.info(f"  Weights: semantic={result['semantic_weight']:.2f}, "
                       f"keyword={result['keyword_weight']:.2f}, "
                       f"proximity={result['proximity_weight']:.2f}")
            logger.info(f"  Duration: {duration:.1f}ms")
        
        # Test 3: Full Hybrid Search (if data exists)
        logger.info("\n=== Testing Hybrid Search Function ===")
        
        # Check if we have data
        chunk_count = await conn.fetchval("SELECT COUNT(*) FROM chunks_jina")
        
        if chunk_count > 0:
            logger.info(f"Found {chunk_count} chunks in database")
            
            # Generate a simple embedding for testing
            embedding_dim = await conn.fetchval("""
                SELECT vector_length(embedding) 
                FROM chunks_jina 
                WHERE embedding IS NOT NULL 
                LIMIT 1
            """)
            
            if embedding_dim:
                logger.info(f"Embedding dimension: {embedding_dim}")
                
                # Create test embedding (normalized random values)
                import random
                test_embedding = [random.random() * 0.1 for _ in range(embedding_dim)]
                
                # Test search
                test_query = "strategic planning implementation"
                logger.info(f"\nSearching for: '{test_query}'")
                
                start = time.time()
                results = await conn.fetch("""
                    SELECT * FROM experimental_hybrid_search_v2($1, $2, 5)
                """, test_query, test_embedding)
                duration = (time.time() - start) * 1000
                
                logger.info(f"✓ Search completed in {duration:.1f}ms")
                logger.info(f"✓ Found {len(results)} results")
                
                if results:
                    for i, row in enumerate(results[:3]):
                        logger.info(f"\nResult {i+1}:")
                        logger.info(f"  Score: {row['final_score']:.3f}")
                        logger.info(f"  Content: {row['content'][:100]}...")
                        logger.info(f"  Source: {row['source']}")
                        
                # Test performance
                logger.info("\n=== Performance Test ===")
                iterations = 10
                total_time = 0
                
                for i in range(iterations):
                    start = time.time()
                    await conn.fetch("""
                        SELECT * FROM experimental_hybrid_search_v2($1, $2, 5)
                    """, test_query, test_embedding)
                    total_time += (time.time() - start) * 1000
                
                avg_time = total_time / iterations
                logger.info(f"✓ Average search time over {iterations} runs: {avg_time:.1f}ms")
                
                if avg_time < 100:
                    logger.info("✅ Performance target MET: <100ms overhead")
                else:
                    logger.warning(f"⚠️ Performance target MISSED: {avg_time:.1f}ms > 100ms")
            else:
                logger.warning("No embeddings found in database")
        else:
            logger.warning("No data in chunks_jina table to test with")
        
        # Test 4: Check indexes
        logger.info("\n=== Checking Indexes ===")
        indexes = await conn.fetch("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename IN ('chunks_jina', 'documents')
            AND schemaname = 'public'
        """)
        
        for idx in indexes:
            logger.info(f"✓ Index: {idx['indexname']}")
        
        logger.info("\n✅ SQL function tests completed!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    asyncio.run(test_sql_functions())
