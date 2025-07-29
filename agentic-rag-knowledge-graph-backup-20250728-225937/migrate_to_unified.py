import asyncpg
import asyncio
import json
from datetime import datetime

async def migrate_chunks():
    conn = await asyncpg.connect('postgresql://neondb_owner:npg_4kfdVM9jQSyI@ep-fancy-meadow-a7kkygxb-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require')
    
    try:
        # Get column info for both tables
        chunks_columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'chunks' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        chunks_unified_columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'chunks_unified' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        print("Chunks table columns:")
        for col in chunks_columns:
            print(f"  {col['column_name']}: {col['data_type']}")
            
        print("\nChunks_unified table columns:")
        for col in chunks_unified_columns:
            print(f"  {col['column_name']}: {col['data_type']}")
            
        # Check if we have data to migrate
        count = await conn.fetchval("SELECT COUNT(*) FROM chunks")
        print(f"\nChunks to migrate: {count}")
        
        if count > 0:
            # Get a sample row to check structure
            sample = await conn.fetchrow("SELECT * FROM chunks LIMIT 1")
            print("\nSample chunk keys:", list(sample.keys()))
            
    finally:
        await conn.close()

asyncio.run(migrate_chunks())
