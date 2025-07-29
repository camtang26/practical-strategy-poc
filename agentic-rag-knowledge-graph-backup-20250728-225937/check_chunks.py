"""Check how many chunks are in the database."""
import asyncio
from agent.db_utils import db_pool, initialize_database

async def check_chunks():
    await initialize_database()
    
    async with db_pool.acquire() as conn:
        # Count total chunks
        total = await conn.fetchval("SELECT COUNT(*) FROM chunks")
        print(f"Total chunks in database: {total}")
        
        # Check documents
        docs = await conn.fetch("""
            SELECT d.title, d.source, COUNT(c.id) as chunk_count
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
            GROUP BY d.id, d.title, d.source
        """)
        
        print("\nDocuments and their chunks:")
        for doc in docs:
            print(f"- {doc['title']}: {doc['chunk_count']} chunks")
        
        # Sample a chunk to check content
        sample = await conn.fetchrow("SELECT content FROM chunks LIMIT 1")
        if sample:
            print(f"\nSample chunk (first 500 chars):")
            print(sample['content'][:500])
            
        # Get total character count
        total_chars = await conn.fetchval("SELECT SUM(LENGTH(content)) FROM chunks")
        if total_chars:
            print(f"\nTotal characters in all chunks: {total_chars:,}")
            print(f"Estimated pages (assuming 3000 chars/page): {total_chars/3000:.0f}")

asyncio.run(check_chunks())
