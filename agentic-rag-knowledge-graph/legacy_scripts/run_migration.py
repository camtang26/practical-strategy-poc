import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def run_migration():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        print("Running migration...")
        with open("migrations/experimental_hybrid_search_v2.sql", "r") as f:
            sql = f.read()
        
        # Execute the migration
        await conn.execute(sql)
        print("✓ Migration completed successfully!")
        
        # Verify functions were created
        functions = await conn.fetch("""
            SELECT proname FROM pg_proc p 
            JOIN pg_namespace n ON p.pronamespace = n.oid 
            WHERE n.nspname = 'public' 
            AND proname IN ('detect_query_intent', 'calculate_dynamic_weights', 'experimental_hybrid_search_v2')
        """)
        
        print(f"✓ Created {len(functions)} functions:")
        for func in functions:
            print(f"  - {func['proname']}")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        await conn.close()

asyncio.run(run_migration())
