import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()

async def update_functions():
    conn = await asyncpg.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB')
    )
    
    try:
        # Drop existing functions with CASCADE to handle dependencies
        print('Dropping existing functions...')
        await conn.execute('DROP FUNCTION IF EXISTS match_chunks CASCADE')
        await conn.execute('DROP FUNCTION IF EXISTS hybrid_search CASCADE')
        
        # Recreate match_chunks with 2048 dimensions
        print('Creating match_chunks function for 2048 dimensions...')
        await conn.execute('''
        CREATE OR REPLACE FUNCTION match_chunks(
            query_embedding vector(2048),
            match_count INT DEFAULT 10
        )
        RETURNS TABLE (
            chunk_id UUID,
            document_id UUID,
            content TEXT,
            similarity FLOAT,
            metadata JSONB,
            document_title TEXT,
            document_source TEXT
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                c.id AS chunk_id,
                c.document_id,
                c.content,
                1 - (c.embedding <=> query_embedding) AS similarity,
                c.metadata,
                d.title AS document_title,
                d.source AS document_source
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$
        ''')
        
        # Recreate hybrid_search with 2048 dimensions
        print('Creating hybrid_search function for 2048 dimensions...')
        await conn.execute('''
        CREATE OR REPLACE FUNCTION hybrid_search(
            query_embedding vector(2048),
            query_text TEXT,
            match_count INT DEFAULT 10,
            text_weight FLOAT DEFAULT 0.3
        )
        RETURNS TABLE (
            chunk_id UUID,
            document_id UUID,
            content TEXT,
            combined_score FLOAT,
            vector_similarity FLOAT,
            text_similarity FLOAT,
            metadata JSONB,
            document_title TEXT,
            document_source TEXT
        )
        LANGUAGE plpgsql
        AS $$
        DECLARE
            max_text_rank FLOAT;
        BEGIN
            -- Get the maximum text rank for normalization
            SELECT MAX(ts_rank_cd(to_tsvector('english', c.content), 
                                  plainto_tsquery('english', query_text)))
            INTO max_text_rank
            FROM chunks c
            WHERE to_tsvector('english', c.content) @@ 
                  plainto_tsquery('english', query_text);
            
            -- Set max_text_rank to 1 if no results to avoid division by zero
            IF max_text_rank IS NULL OR max_text_rank = 0 THEN
                max_text_rank := 1;
            END IF;
            
            RETURN QUERY
            WITH vector_search AS (
                SELECT 
                    c.id,
                    c.document_id,
                    c.content,
                    c.metadata,
                    1 - (c.embedding <=> query_embedding) AS similarity,
                    d.title,
                    d.source
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> query_embedding
                LIMIT match_count * 2  -- Get more candidates for hybrid scoring
            ),
            text_search AS (
                SELECT 
                    c.id,
                    c.document_id,
                    c.content,
                    c.metadata,
                    ts_rank_cd(to_tsvector('english', c.content), 
                              plainto_tsquery('english', query_text)) / max_text_rank AS rank,
                    d.title,
                    d.source
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE to_tsvector('english', c.content) @@ 
                      plainto_tsquery('english', query_text)
                ORDER BY rank DESC
                LIMIT match_count * 2
            )
            SELECT DISTINCT ON (COALESCE(v.id, t.id))
                COALESCE(v.id, t.id) AS chunk_id,
                COALESCE(v.document_id, t.document_id) AS document_id,
                COALESCE(v.content, t.content) AS content,
                -- Combined score
                (
                    COALESCE(v.similarity, 0) * (1 - text_weight) + 
                    COALESCE(t.rank, 0) * text_weight
                ) AS combined_score,
                COALESCE(v.similarity, 0) AS vector_similarity,
                COALESCE(t.rank, 0) AS text_similarity,
                COALESCE(v.metadata, t.metadata) AS metadata,
                COALESCE(v.title, t.title) AS document_title,
                COALESCE(v.source, t.source) AS document_source
            FROM vector_search v
            FULL OUTER JOIN text_search t ON v.id = t.id
            ORDER BY 
                COALESCE(v.id, t.id),
                combined_score DESC
            LIMIT match_count;
        END;
        $$
        ''')
        
        print('Successfully updated all functions to support 2048 dimensions!')
        
    except Exception as e:
        print(f'Error: {e}')
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(update_functions())
