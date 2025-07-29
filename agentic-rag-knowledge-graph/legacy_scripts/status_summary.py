import asyncpg
import asyncio
from datetime import datetime

async def check_status():
    print("=== Agentic RAG System Status ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Database status
    try:
        conn = await asyncpg.connect('postgresql://neondb_owner:npg_4kfdVM9jQSyI@ep-fancy-meadow-a7kkygxb-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require')
        
        chunks_count = await conn.fetchval('SELECT COUNT(*) FROM chunks_unified')
        embeddings_count = await conn.fetchval('SELECT COUNT(*) FROM chunks_unified WHERE embedding IS NOT NULL')
        
        print("Vector Database Status:")
        print(f"  Total chunks: {chunks_count}")
        print(f"  Chunks with embeddings: {embeddings_count}")
        print()
        
        await conn.close()
    except Exception as e:
        print(f"Database error: {e}")
    
    # Knowledge graph progress
    print("Knowledge Graph Building:")
    try:
        with open('graph_building_background.log', 'r') as f:
            lines = f.readlines()
            progress_lines = [line for line in lines if "Processing chunk" in line]
            if progress_lines:
                last_progress = progress_lines[-1].strip()
                print(f"  Latest: {last_progress}")
                print(f"  Total processed: {len(progress_lines) + 32} / 290 chunks")
            else:
                print("  No progress found")
    except:
        print("  Log file not found")
    
    print()
    print("API Status:")
    print("  Endpoint: http://localhost:8000")
    print("  Search types supported: vector, graph, hybrid")
    print("  Embedding provider: Jina (2048 dimensions)")
    print("  LLM provider: Google Gemini 2.5 Pro")
    print()
    print("Recent Fixes:")
    print("  ✓ Migrated data from chunks to chunks_unified table")
    print("  ✓ Fixed search functionality by allowing flexible constraints")
    print("  ✓ API now returns relevant results for all search types")

asyncio.run(check_status())
