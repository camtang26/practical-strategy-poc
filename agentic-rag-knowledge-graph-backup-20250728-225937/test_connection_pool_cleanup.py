"""Test connection pool cleanup in FastAPI lifespan."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import httpx

sys.path.append(str(Path(__file__).parent))

# Set required environment variables
os.environ["EMBEDDING_API_KEY"] = "test_key"
os.environ["EMBEDDING_BASE_URL"] = "https://api.jina.ai/v1"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"


async def test_embedder_cleanup():
    """Test that embedder cleanup is called during shutdown."""
    
    # Import after env vars are set
    from agent.providers_extended import get_embedder, cleanup_embedder, _embedder_instance
    
    # Get the embedder to initialize it
    embedder = await get_embedder()
    assert embedder is not None
    assert embedder._client is None  # Not initialized yet
    
    # Force client creation
    client = await embedder._get_client()
    assert client is not None
    assert isinstance(client, httpx.AsyncClient)
    assert embedder._client is not None
    
    # Call cleanup
    await cleanup_embedder()
    
    # Verify cleanup worked
    assert embedder._client is None, "Client not cleaned up!"
    print("✅ Embedder cleanup test passed!")


async def test_api_lifespan_cleanup():
    """Test that the API lifespan handler calls cleanup_embedder."""
    
    # Mock the database and graph functions
    with patch('agent.api.initialize_database', new_callable=AsyncMock) as mock_init_db, \
         patch('agent.api.initialize_graph', new_callable=AsyncMock) as mock_init_graph, \
         patch('agent.api.test_connection', new_callable=AsyncMock) as mock_test_db, \
         patch('agent.api.test_graph_connection', new_callable=AsyncMock) as mock_test_graph, \
         patch('agent.api.close_database', new_callable=AsyncMock) as mock_close_db, \
         patch('agent.api.close_graph', new_callable=AsyncMock) as mock_close_graph, \
         patch('agent.api.cleanup_embedder', new_callable=AsyncMock) as mock_cleanup_embedder:
        
        # Set up mock returns
        mock_test_db.return_value = True
        mock_test_graph.return_value = True
        
        # Import and create app
        from agent.api import lifespan, FastAPI
        
        # Create a test app with the lifespan
        app = FastAPI(lifespan=lifespan)
        
        # Simulate startup and shutdown
        async with lifespan(app):
            # Startup phase
            assert mock_init_db.called
            assert mock_init_graph.called
            
        # After exiting context, shutdown should have been called
        assert mock_cleanup_embedder.called, "cleanup_embedder not called during shutdown!"
        assert mock_close_db.called
        assert mock_close_graph.called
        
        print("✅ API lifespan cleanup test passed!")


async def test_embedder_singleton_cleanup():
    """Test that the embedder singleton is properly reset after cleanup."""
    
    from agent import providers_extended
    
    # Reset the singleton
    providers_extended._embedder_instance = None
    
    # Get embedder (creates new instance)
    embedder1 = await providers_extended.get_embedder()
    
    # Get again (should return same instance)
    embedder2 = await providers_extended.get_embedder()
    assert embedder1 is embedder2, "Singleton not working!"
    
    # Initialize the client
    await embedder1._get_client()
    assert embedder1._client is not None
    
    # Cleanup
    await providers_extended.cleanup_embedder()
    
    # Verify singleton was reset
    assert providers_extended._embedder_instance is None, "Singleton not reset!"
    
    # Get embedder again (should create new instance)
    embedder3 = await providers_extended.get_embedder()
    assert embedder3 is not embedder1, "Singleton not recreated after cleanup!"
    
    # Cleanup
    await embedder3.close()
    
    print("✅ Embedder singleton cleanup test passed!")


async def test_concurrent_cleanup():
    """Test that cleanup handles concurrent calls correctly."""
    
    from agent.providers_extended import get_embedder, cleanup_embedder
    
    # Get embedder
    embedder = await get_embedder()
    await embedder._get_client()
    
    # Call cleanup concurrently multiple times
    tasks = [cleanup_embedder() for _ in range(5)]
    await asyncio.gather(*tasks)
    
    # Verify it's still cleaned up properly
    assert embedder._client is None
    
    print("✅ Concurrent cleanup test passed!")


if __name__ == "__main__":
    print("Testing connection pool cleanup...")
    asyncio.run(test_embedder_cleanup())
    asyncio.run(test_api_lifespan_cleanup())
    asyncio.run(test_embedder_singleton_cleanup())
    asyncio.run(test_concurrent_cleanup())
    print("\n🎉 All connection pool cleanup tests passed!")
