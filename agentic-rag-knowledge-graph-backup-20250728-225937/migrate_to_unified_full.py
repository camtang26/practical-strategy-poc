import asyncpg
import asyncio
from datetime import datetime

async def migrate_chunks():
    conn = await asyncpg.connect('postgresql://neondb_owner:npg_4kfdVM9jQSyI@ep-fancy-meadow-a7kkygxb-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require')
    
    try:
        # Check current state
        chunks_count = await conn.fetchval("SELECT COUNT(*) FROM chunks")
        unified_count = await conn.fetchval("SELECT COUNT(*) FROM chunks_unified")
        
        print(f"Current state:")
        print(f"  chunks table: {chunks_count} rows")
        print(f"  chunks_unified table: {unified_count} rows")
        
        if chunks_count > 0 and unified_count == 0:
            print("\nMigrating data from chunks to chunks_unified...")
            
            # Perform the migration
            result = await conn.execute("""
                INSERT INTO chunks_unified (
                    id, document_id, chunk_index, content, embedding,
                    embedding_model, embedding_provider, embedding_dim,
                    metadata, created_at, updated_at
                )
                SELECT 
                    id, 
                    document_id, 
                    chunk_index, 
                    content, 
                    embedding,
                    'text-embedding-v4' as embedding_model,
                    'jina' as embedding_provider,
                    2048 as embedding_dim,
                    metadata,
                    created_at,
                    created_at as updated_at
                FROM chunks
                WHERE embedding IS NOT NULL
            """)
            
            # Get the number of rows inserted
            rows_inserted = int(result.split()[-1])
            print(f"Migrated {rows_inserted} rows successfully!")
            
            # Verify migration
            new_count = await conn.fetchval("SELECT COUNT(*) FROM chunks_unified")
            embeddings_count = await conn.fetchval("SELECT COUNT(*) FROM chunks_unified WHERE embedding IS NOT NULL")
            
            print(f"\nVerification:")
            print(f"  chunks_unified total rows: {new_count}")
            print(f"  chunks_unified with embeddings: {embeddings_count}")
            
            # Get a sample to verify
            sample = await conn.fetchrow("""
                SELECT id, embedding_model, embedding_provider, embedding_dim, 
                       octet_length(embedding::text) as embedding_size
                FROM chunks_unified 
                LIMIT 1
            """)
            
            if sample:
                print(f"\nSample migrated row:")
                print(f"  id: {sample['id']}")
                print(f"  embedding_model: {sample['embedding_model']}")
                print(f"  embedding_provider: {sample['embedding_provider']}")
                print(f"  embedding_dim: {sample['embedding_dim']}")
                print(f"  embedding size: {sample['embedding_size']} bytes")
            
        else:
            print("\nMigration not needed or already done.")
            
    except Exception as e:
        print(f"Error during migration: {e}")
        
    finally:
        await conn.close()

asyncio.run(migrate_chunks())
