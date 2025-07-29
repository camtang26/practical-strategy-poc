import asyncio
import json
from agent.providers_extended import generate_embedding_unified
from agent.db_utils import db_pool
from agent.providers import get_embedding_provider

async def test_search():
    # Initialize db pool
    await db_pool.initialize()
    
    # Generate embedding for query
    query = "What is practical strategy?"
    print(f"Generating embedding for: {query}")
    
    try:
        embedding = await generate_embedding_unified(query)
        print(f"Embedding generated, length: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return
    
    # Test direct SQL query
    async with db_pool.acquire() as conn:
        # Check we have the right provider
        provider = get_embedding_provider()
        print(f"Using provider: {provider}")
        
        # Test match_chunks_unified function
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        try:
            results = await conn.fetch("""
                SELECT * FROM match_chunks_unified($1::vector, $2, $3)
            """, embedding_str, provider, 5)
            
            print(f"\nSearch results: {len(results)} found")
            for i, row in enumerate(results):
                print(f"\nResult {i+1}:")
                print(f"  Similarity: {row['similarity']}")
                print(f"  Content preview: {row['content'][:200]}...")
                
        except Exception as e:
            print(f"Error in search: {e}")
            
            # Try direct query without function
            try:
                results = await conn.fetch("""
                    SELECT 
                        c.id,
                        c.content,
                        1 - (c.embedding <=> $1::vector) as similarity
                    FROM chunks_unified c
                    WHERE c.embedding_provider = $2
                    ORDER BY c.embedding <=> $1::vector
                    LIMIT 5
                """, embedding_str, provider)
                
                print(f"\nDirect query results: {len(results)} found")
                for i, row in enumerate(results):
                    print(f"\nResult {i+1}:")
                    print(f"  Similarity: {row['similarity']}")
                    print(f"  Content preview: {row['content'][:200]}...")
                    
            except Exception as e2:
                print(f"Error in direct query: {e2}")
    
    await db_pool.close()

asyncio.run(test_search())
