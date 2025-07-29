import asyncio
from agent.database import get_db_connection

async def check_content():
    conn = await get_db_connection()
    
    # Check documents
    print("=== DOCUMENTS IN DATABASE ===")
    result = await conn.fetch("SELECT id, title, source, created_at FROM documents")
    for doc in result:
        print(f"Document: {doc['title']} (ID: {doc['id']}, Source: {doc['source']})")
        
        # Count chunks
        chunk_count = await conn.fetchval(
            "SELECT COUNT(*) FROM chunks WHERE document_id = $1", 
            doc['id']
        )
        print(f"  Chunks: {chunk_count}")
    
    # Total chunks
    print("\n=== TOTAL CHUNKS ===")
    total_chunks = await conn.fetchval("SELECT COUNT(*) FROM chunks")
    print(f"Total chunks in database: {total_chunks}")
    
    # Check chunk lengths
    print("\n=== CHUNK STATISTICS ===")
    avg_length = await conn.fetchval("SELECT AVG(LENGTH(content)) FROM chunks")
    max_length = await conn.fetchval("SELECT MAX(LENGTH(content)) FROM chunks")
    print(f"Average chunk length: {avg_length:.0f} chars")
    print(f"Max chunk length: {max_length} chars")
    
    await conn.close()

asyncio.run(check_content())
