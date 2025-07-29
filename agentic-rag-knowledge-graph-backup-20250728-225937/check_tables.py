import asyncpg
import asyncio

async def check():
    conn = await asyncpg.connect('postgresql://neondb_owner:npg_4kfdVM9jQSyI@ep-fancy-meadow-a7kkygxb-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require')
    tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    print('Tables:', [t['tablename'] for t in tables])
    
    # Check chunks table
    try:
        chunks_count = await conn.fetchval('SELECT COUNT(*) FROM chunks')
        print(f'chunks table count: {chunks_count}')
        # Check if embeddings exist
        embeddings_count = await conn.fetchval('SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL')
        print(f'chunks with embeddings: {embeddings_count}')
    except Exception as e:
        print(f'chunks table error: {e}')
    
    # Check chunks_unified table  
    try:
        chunks_unified_count = await conn.fetchval('SELECT COUNT(*) FROM chunks_unified')
        print(f'chunks_unified table count: {chunks_unified_count}')
    except Exception as e:
        print(f'chunks_unified table error: {e}')
        
    await conn.close()

asyncio.run(check())
